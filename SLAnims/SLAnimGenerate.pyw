#!/usr/bin/python3
"""
This script reads the files in SLAnims\source, and generates JSON output in
SLAnims\json which can be read by SLAnimLoader in Skyrim.

While you could manually edit the JSON data by hand, JSON is not very friendly
to hand-edit.  (It is easy to break if you don't get the syntax exactly right,
and you won't get any feedback in Skyrim if you break anything.)  The source
scripts also allow animation info to be specified in a much less verbose
format.
"""
import argparse
import inspect
import json
import os
import re
import sys
import traceback


#################################
# Helpers for use in source files
#################################

# Several functions available in scripts are actually methods of Category.
# - Animation() is Category.add_anim()
# - anim_id_prefix() is Category.set_anim_id_prefix()
# - anim_name_prefix() is Category.set_anim_name_prefix()
# - common_tags() is Category.set_common_tags()

# SexLab currently supports up to 5 actors
MAX_ACTORS = 5

VALID_SOUNDS = [
    "",
    "none",
    "Squishing",
    "Sucking",
    "SexMix",
    "Squirting",
]

# These numerical values must match the settings defined
# in the SexLab Framework's sslAnimationFactory script.
CUM_TYPES = {
    "Vaginal": 1,
    "Oral": 2,
    "Anal": 3,
    "VaginalOral": 4,
    "VaginalAnal": 5,
    "OralAnal": 6,
    "VaginalOralAnal": 7,
}
CUM_TYPES_LOWER = dict((k.lower(), v) for k, v in CUM_TYPES.items())

KNOWN_RACES = {
    #
    # Races added by SexLab Framework
    #
    "Bears": "bear",
    "Chaurus": "chaurus",
    "Chickens": "ambient/chicken",
    "Dogs": "canine",
    "Dragons": "dragon",
    "Draugrs": "draugr",
    "Falmers": "falmer",
    "FlameAtronach": "atronachflame",
    "Gargoyles": "dlc01/vampirebrute",
    "Giants": "giant",
    "Horses": "horse",
    "LargeSpiders": "frostbitespider",
    "Lurkers": "dlc02/benthiclurker",
    "Rieklings": "dlc02/riekling",
    "SabreCats": "sabrecat",
    "Seekers": "dlc02/hmdaedra",
    "Skeevers": "skeever",
    "Spiders": "frostbitespider",
    "Spriggans": "spriggan",
    "Trolls": "troll",
    "VampireLords": "vampirelord",
    "Werewolves": "werewolfbeast",
    "Wolves": "canine",
    #
    # Races added by MoreNastyCritters
    #
    "Ashhoppers": "dlc02/scrib",
    "Boars": "dlc02/boarriekling",
    "ChaurusHunters": "dlc01/chaurusflyer",
    "ChaurusReapers": "chaurus",
    "Cows": "cow",
    "Deers": "deer",
    "DragonPriests": "dragonpriest",
    "DwarvenBallistas": "dlc02\dwarvenballistacenturion",
    "DwarvenCenturions": "DwarvenSteamCenturion",
    "DwarvenSpheres": "dwarvenspherecenturion",
    "DwarvenSpiders": "dwarvenspider",
    "FrostAtronach": "atronachfrost",
    "Goats": "goat",
    "Hagravens": "hagraven",
    "Horkers": "horker",
    "Mammoths": "mammoth",
    "Netches": "dlc02/netch",
    "Rabbits": "ambient/hare",
    "Slaughterfishes": "slaughterfish",
    "GiantSpiders": "frostbitespider",
    "Wispmothers": "wisp",
}
KNOWN_RACES_LOWER = dict((k.lower(), v) for k, v in KNOWN_RACES.items())


class Stage(object):
    def __init__(self, number, **kwargs):
        self.number = number
        self.kwargs = kwargs


class Actor(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class Male(Actor):
    SEXLAB_VALUE = 0
    ALLOW_CUM = False
    IS_CREATURE = False


class Female(Actor):
    SEXLAB_VALUE = 1
    ALLOW_CUM = True
    IS_CREATURE = False


class CreatureMale(Actor):
    SEXLAB_VALUE = 2
    ALLOW_CUM = False
    IS_CREATURE = True


class CreatureFemale(Actor):
    SEXLAB_VALUE = 3
    ALLOW_CUM = True
    IS_CREATURE = True


###################################################
# End Helpers
# The remaining code is the rebuilding logic itself
###################################################

__LOADER_CODE__ = None

_ANIM_NAME_REGEX = re.compile(r"(?P<name>.*)A(?P<actor>[0-9]+)"
                              r"(?:_?S(?P<stage>[0-9]+))?$",
                              re.IGNORECASE)


class Category(object):
    def __init__(self, name, src_path, data_dir):
        self.name = name
        self.src_path = src_path
        self.data_dir = data_dir

        self.json_path = os.path.join(self.data_dir, "SLAnims", "json",
                                      self.name + ".json")

        self.mcm_name = name
        self.anim_dir = name

        # The Example.txt sample file sets is_example to true.
        # We skip any file with is_example set when processing files.
        self.is_example = False

        self.errors = []
        self.anim_errors = 0
        self.anims = []
        self.anims_by_id = {}
        self.anim_id_prefix = ""
        self.anim_name_prefix = ""
        self.common_tags = []

        self.fnis_changed = {}

    @classmethod
    def load(cls, path):
        # Parse the path name to get the category name
        # and the main data directory.
        src_dir, base = os.path.split(path)
        cat_name, ext = os.path.splitext(base)
        parts = os.path.abspath(src_dir).split(os.path.sep)
        if len(parts) < 2 or parts[-2].lower() != "slanims":
            raise Exception(r"source files should be inside an "
                            r"SLAnims\data directory")
        data_dir = os.path.sep.join(parts[:-2])

        cat = cls(cat_name, path, data_dir)

        try:
            cls._load_impl(cat, path)
        except Exception as ex:
            err_lines = traceback.format_exception(*sys.exc_info())
            cat.errors.extend(err_lines)
            return cat

        return cat

    def relpath(self, path):
        return os.path.relpath(path, self.data_dir)

    @classmethod
    def _load_impl(cls, cat, path):
        # Read the source file contents
        with open(path, "rb") as f:
            data = f.read()

        try:
            code = compile(data, path, "exec")
        except SyntaxError as ex:
            err_lines = traceback.format_exception_only(type(ex), ex)
            cat.errors.extend(err_lines)
            return

        local_vars = {}
        global_vars = {
            "Animation": cat.add_anim,
            "anim_dir": cat.set_anim_dir,
            "anim_id_prefix": cat.set_anim_id_prefix,
            "anim_name_prefix": cat.set_anim_name_prefix,
            "common_tags": cat.set_common_tags,
            "Stage": Stage,
            "Female": Female,
            "Male": Male,
            "CreatureFemale": CreatureFemale,
            "CreatureMale": CreatureMale,
            "__CATEGORY_FRAME__": None,
        }

        for sound in VALID_SOUNDS:
            if not sound:
                continue
            if sound == "none":
                global_vars["NoSound"] = sound
            else:
                global_vars[sound] = sound
        for cum_type in CUM_TYPES.keys():
            global_vars[cum_type] = cum_type
        exec(code, global_vars, local_vars)

        mcm_name = local_vars.get("mcm_name")
        if mcm_name is not None:
            cat.mcm_name = mcm_name

        cat.is_example = local_vars.get("is_example", False)

        cat.load_stages()
        cat.anim_errors = sum(1 for a in cat.anims if a.errors)

        cat.gen_data()

    def gen_data(self):
        self.json = self.gen_json_dict()
        self.old_json = self._read_json()
        self.fnis_info = self.gen_fnis_lines()

        self._check_fnis_same()

    def _check_fnis_same(self):
        fnis_changed = {}
        for path, new_lines in self.fnis_info.items():
            try:
                with open(path, "r") as f:
                    old_data = f.read()
            except OSError:
                old_data = ""

            old_info = self._parse_fnis_lines(old_data.splitlines())
            new_info = self._parse_fnis_lines(new_lines)
            if old_info == new_info:
                continue

            fnis_changed[path] = (old_info, new_info)

        self.fnis_changed = fnis_changed

    def _parse_fnis_lines(self, lines):
        stages = {}
        untitled = set()
        title = None
        cur_stage = []

        def stage_finished():
            if not cur_stage:
                return
            if title:
                stages[title] = cur_stage
            else:
                untitled.add(tuple(cur_stage))

        for line in lines:
            l = line.strip()
            if not l:
                stage_finished()
                title = None
                continue
            if l.startswith("'"):
                title = l[1:].strip()
                continue

            if l.startswith("s"):
                stage_finished()
                cur_stage = [l]
            if l.startswith("+"):
                assert(cur_stage)
                cur_stage.append(l)

        stage_finished()
        return stages, untitled

    def save_all(self):
        self.save_json()
        self.save_all_fnis()

    def save_json(self):
        try:
            os.makedirs(os.path.dirname(self.json_path))
        except OSError as ex:
            pass

        with open(self.json_path, "w") as f:
            json.dump(self.json, f, indent=2, sort_keys=True)
        self.old_json = self.json

    def save_all_fnis(self):
        for path, lines in self.fnis_info.items():
            data = "\n".join(lines) + "\n"
            with open(path, "w") as f:
                f.write(data)

        self.fnis_changed.clear()

    def save_fnis(self, path):
        lines = self.fnis_info[path]
        data = "\n".join(lines) + "\n"
        with open(path, "w") as f:
            f.write(data)

        self.fnis_changed.pop(path, None)

    def set_anim_dir(self, path):
        self.anim_dir = path

    def add_anim(self, id, name, **kwargs):
        full_id = self.anim_id_prefix + id
        name = self.anim_name_prefix + name

        anim = AnimInfo(self, full_id, name, **kwargs)
        anim.bare_id = id
        self.anims.append(anim)

        if anim.id in self.anims_by_id:
            anim.error("duplicate animation ID {}", anim.id)
        else:
            self.anims_by_id[anim.id] = anim

    def set_anim_id_prefix(self, prefix):
        self.anim_id_prefix = prefix

    def set_anim_name_prefix(self, prefix):
        self.anim_name_prefix = prefix

    def set_common_tags(self, tags):
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        self.common_tags = tags

    def _read_json(self):
        try:
            with open(self.json_path, "r") as f:
                return json.load(f)
        except:
            return {}

    def load_stages(self):
        dir_caches = {}
        for anim in self.anims:
            anim.load_stages(dir_caches)

    def gen_json_dict(self):
        anims = []
        for anim in self.anims:
            anims.append(anim.gen_json_dict())

        d = {
            "name": self.mcm_name,
            "animations": anims,
        }
        return d

    def gen_fnis_lines(self):
        lines_by_path = {}
        for anim in self.anims:
            anim_lines_by_path = anim.gen_fnis_lines()
            for path, anim_lines in anim_lines_by_path.items():
                if path not in lines_by_path:
                    lines_by_path[path] = ["Version V1.0"]
                lines = lines_by_path[path]

                lines.append("")
                lines.extend(anim_lines)

        return lines_by_path

    def anim_error(self, anim, msg, *args, **kwargs):
        if args or kwargs:
            msg = msg.format(*args, **kwargs)

        err_lines = [msg + ":"] + self._get_source_stack_info()
        anim.errors.extend(err_lines)

    def _get_source_stack_info(self):
        # Return the stack frames that are part of the config code rather
        # than our code.
        f = inspect.currentframe()
        stack_info = []
        while f:
            if "__LOADER_CODE__" in f.f_globals:
                break
            stack_info.extend(traceback.extract_stack(f, 1))
            f = f.f_back

        return [l.rstrip() for l in traceback.format_list(stack_info)]


class AnimStageFile(object):
    def __init__(self, path, anim_id, actor, stage):
        self.path = path
        self.anim_id = anim_id
        self.actor = actor
        self.stage = stage
        self.used = False


class AnimDirCache(object):
    """
    AnimDirCache finds all hkx files in a given directory, and parses
    name, actor, and stage information out of them.
    """
    def __init__(self, path):
        self.path = path

        self._by_name = {}
        self._load()

    def get_anims(self, *names):
        results = []
        for n in names:
            anims = self._by_name.get(n.lower())
            if not anims:
                continue
            results.extend(anims)
        return results

    def _load(self):
        try:
            dir_entries = os.listdir(self.path)
        except OSError:
            # The directory doesn't exist, or we didn't have permission to read
            # it, or some other similar error.
            return

        for entry in dir_entries:
            base, ext = os.path.splitext(entry)
            if ext.lower() != ".hkx":
                continue

            m = _ANIM_NAME_REGEX.match(base)
            if not m:
                continue

            name = m.group("name").lower()
            name = name.rstrip("_")

            actor_num = int(m.group("actor"))

            stage_str = m.group("stage")
            if stage_str is None:
                stage_num = 1
            else:
                stage_num = int(stage_str)

            name_info = self._by_name.get(name)
            if name_info is None:
                name_info = []
                self._by_name[name] = name_info

            entry_path = os.path.join(self.path, entry)
            anim_info = AnimStageFile(entry_path, name, actor_num, stage_num)
            name_info.append(anim_info)


class AnimInfo(object):
    def __init__(self, cat, id, name, **kwargs):
        self.category = cat
        self.errors = []

        self.id = id
        self.name = name
        self.anim_dir = cat.anim_dir
        self.sound = kwargs.pop("sound", None)
        if self.sound is None:
            # TODO: This is okay if a sound is explicitly specified
            # for each stage
            self.error("no animation sound specified")
        elif self.sound not in VALID_SOUNDS:
            self.error("invalid sound {!r}: must be one of {}",
                       self.sound, ", ".join(VALID_SOUNDS))

        # Parse tags
        tags_arg = kwargs.pop("tags", None)
        self.tags = cat.common_tags[:]
        if tags_arg is None:
            if not cat.common_tags:
                self.error("no animation tags specified")
        else:
            self.tags.extend(self._parse_tags(tags_arg))

        # Parse actors
        self.creature_race = None
        self.actors = []
        missing_actors = []
        for n in range(1, MAX_ACTORS + 1):
            arg_name = "actor{}".format(n)
            stage_arg_name = "a{}_stage_params".format(n)
            info = kwargs.pop(arg_name, None)
            stage_params = kwargs.pop(stage_arg_name, None)
            if info is None:
                missing_actors.append(arg_name)
                if stage_params is not None:
                    self.error("cannot specify {} without {}",
                               stage_arg_name, arg_name)
                continue
            if missing_actors:
                # This happens if there is a missing actor.
                # e.g., actor1 and actor3 were specified, but not actor2
                self.error("cannot specify {} without {}",
                           arg_name, ", ".join(missing_actors))
                continue

            actor_info = ActorInfo(self, n, info, stage_params)
            if actor_info.creature_race is not None:
                self.creature_race = actor_info.creature_race
            self.actors.append(actor_info)

        if not self.actors:
            self.error("must include at least one actor")

        # Parse stage_params
        stage_params_arg = kwargs.pop("stage_params", None)
        self.stage_params = self._parse_stage_params(stage_params_arg)

        if kwargs:
            self.error("unsupported arguments: {}", "," .join(kwargs.keys()))

    def error(self, msg, *args, **kwargs):
        if args or kwargs:
            msg = msg.format(*args, **kwargs)

        stack_info = self.category._get_source_stack_info()
        if stack_info:
            self.errors.append(msg + ":")
            self.errors.extend("  " + line for line in stack_info)
        else:
            self.errors.append(msg)

    def _parse_tags(self, tags):
        if isinstance(tags, (list, tuple)):
            return list(tags)
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",")]

        raise Exception("bad tags value: must be a list or string")

    def _parse_stage_params(self, stage_params):
        VALID_ARGS = {
            "sound": str,
            "timer": float,
        }
        parsed = _parse_stage_params(stage_params, VALID_ARGS,
                                     on_error=self.error)
        # Validate the sound types
        for sp in parsed.values():
            sp_sound = sp.get("sound")
            if sp_sound is not None and sp_sound not in VALID_SOUNDS:
                self.error("invalid sound {!r}: must be one of {}",
                           self.sound, ", ".join(VALID_SOUNDS))

        return parsed

    def load_stages(self, dir_caches):
        if not self.actors:
            return

        for actor in self.actors:
            actor.find_anim_files(dir_caches)

        num_stages = len(self.actors[0].stage_anims)
        bad = False
        stage_by_actor = [("A1", num_stages)]
        for idx, actor in enumerate(self.actors[1:]):
            n = len(actor.stage_anims)
            stage_by_actor.append(("A{}".format(idx + 2), n))
            if n != num_stages:
                bad = True
                num_stages = max(n, num_stages)
        if bad:
            self.error("all actors must have the same number of "
                       "animation stages: {}", stage_by_actor)

        for stage_num in self.stage_params.keys():
            if stage_num <= 0 or stage_num > num_stages:
                self.error("invalid stage number {} in stage_params",
                           stage_num)

    def gen_json_dict(self):
        actor_data = []
        for actor in self.actors:
            actor_data.append(actor.gen_json_dict())

        d = {
            "id": self.id,
            "name": self.name,
        }
        if self.errors:
            d["error"] = "\n".join(self.errors)
            return d

        d.update(tags=",".join(self.tags),
                 sound=self.sound,
                 actors=actor_data)
        if self.creature_race:
            d["creature_race"] = self.creature_race
        if self.stage_params:
            sp = []
            for stage_num, info in self.stage_params.items():
                json_info = info.copy()
                json_info['number'] = stage_num
                sp.append(json_info)
            d["stages"] = sp
        return d

    def gen_fnis_lines(self):
        lines_by_path = {}
        for actor in self.actors:
            fnis_path = actor.get_fnis_list_path()
            if fnis_path not in lines_by_path:
                lines = ["' {}".format(self.id)]
                lines_by_path[fnis_path] = lines
            else:
                lines = lines_by_path[fnis_path]

            lines.extend(actor.gen_fnis_lines())

        return lines_by_path


class ActorInfo(object):
    ACTOR_STAGE_ARGS = {
        "forward": float,
        "up": float,
        "side": float,
        "rotate": float,
        "silent": bool,
        "open_mouth": bool,
        "strap_on": bool,
        "sos": int,
    }

    def __init__(self, anim, number, info, stage_params):
        self.anim = anim
        self.number = number

        # This will eventually be set to an array containing the animation path
        # for each animation stage.
        self.stage_anims = None

        self.creature_race = None
        self.anim_race_dir = None

        # Check to make sure the argument is a valid Actor type
        if not hasattr(info, "ALLOW_CUM"):
            self.error("invalid actor type")
            # We shouldn't try generating JSON for this animation
            # due to the error, but set a default type just in case.
            self.type = Male
            return
        self.type = type(info).__name__

        # Allow users to pass in an Actor class instead of an instance object.
        # This makes it okay to use "Male" instead of "Male()" when there
        # aren't any extra arguments that need to be specified.
        kwargs = getattr(info, "kwargs", {})

        if getattr(info, "IS_CREATURE", False):
            self.creature_race = kwargs.pop("race", None)
            if self.creature_race is None:
                self.error("race argument must be given for "
                           "creature actor types")
            elif self.creature_race.lower() not in KNOWN_RACES_LOWER.keys():
                # This is not necessarily an error, since other mods
                # can register creature race IDs.  However, it does
                # mean we probably won't know where to look for the
                # animation files.
                self.warning("unknown creature race {!r}: "
                             "did you mean one of {}",
                             self.creature_race, ", ".join(KNOWN_RACES))

        self.anim_race_dir = kwargs.pop("anim_race_dir", None)

        self.cum = None
        cum_type = kwargs.pop("add_cum", None)
        if cum_type is not None:
            self.cum = CUM_TYPES_LOWER.get(cum_type.lower())
            if self.cum is None:
                self.error("invalid cum type {!r}: must be one of {}",
                           cum_type, ", ".join(CUM_TYPES.keys()))

        self.object_name = kwargs.pop("object", None)

        self.stage_defaults = _parse_stage_args(kwargs, self.ACTOR_STAGE_ARGS,
                                                on_error=self.error)
        if kwargs:
            self.error("unsupported arguments: {}", ", ".join(kwargs.keys()))

        self.stage_params = self._parse_stage_params(stage_params)

    def _parse_stage_params(self, stage_params):
        def on_error(msg, *args, **kwargs):
            if args or kwargs:
                msg = msg.format(*args, **kwargs)
            self.error("a{}_stage_params: {}", self.number, msg)

        parsed = _parse_stage_params(stage_params, self.ACTOR_STAGE_ARGS,
                                     on_error=on_error)
        return parsed

    def get_anim_dir(self):
        data_dir = self.anim.category.data_dir
        race_dir = self._get_race_dir()
        return os.path.join(data_dir, "meshes", "actors", race_dir,
                            "animations", self.anim.anim_dir)

    def find_anim_files(self, dir_caches):
        anim_dir = self.get_anim_dir()

        dir_cache = dir_caches.get(anim_dir.lower())
        if dir_cache is None:
            dir_cache = AnimDirCache(anim_dir)
            dir_caches[anim_dir.lower()] = dir_cache

        # Since the animation directory already include mod information,
        # allow the animation files to not include the ID prefix.
        #
        # e.g. even though we may add an "FB_" prefix to all animation IDs
        # in the FunnyBizness category, allow
        #   actors/character/animations/FunnyBizness/HardcoreDoggy_A1_S1.hkx
        # in addition to
        #   actors/character/animations/FunnyBizness/FB_HardcoreDoggy_A1_S1.hkx
        by_stage = {}
        anims = dir_cache.get_anims(self.anim.id, self.anim.bare_id)
        for info in anims:
            if info.actor != self.number:
                continue

            if info.stage in by_stage:
                self.error("found multiple animations for stage {}:\n"
                           "  - {}\n"
                           "  - {}",
                           info.stage, by_stage[info.stage], info.path)
            by_stage[info.stage] = info.path

        expected_next = 1
        stages = []
        for n in sorted(by_stage.keys()):
            if n != expected_next:
                self.error("no animation found for stage {}", expected_next)
                self.stage_anims = []
                return
            expected_next += 1
            stages.append(by_stage[n])

        if not stages:
            self.error("no animations found: expected animations "
                       "at {}\\{}_A{}_S1.hkx",
                       anim_dir, self.anim.id, self.number)

        self.stage_anims = stages

    def get_fnis_list_path(self):
        fnis_dir = self.get_anim_dir()
        race_name = fnis_dir.split(os.path.sep)[-3]
        if race_name.lower() == "character":
            entry = "FNIS_{}_List.txt".format(self.anim.anim_dir)
        else:
            entry = "FNIS_{}_{}_List.txt".format(self.anim.anim_dir, race_name)
        return os.path.join(fnis_dir, entry)

    def _get_race_dir(self):
        if self.anim_race_dir is not None:
            return self.anim_race_dir

        if self.creature_race is None:
            return "character"

        race_dir = KNOWN_RACES_LOWER.get(self.creature_race.lower())
        if race_dir is None:
            self.error("unable to find animation race directory for unknown "
                       "race {}.  You can add an anim_race_dir parameter to "
                       "{}.actor{} to tell us where to find it for now",
                       self.creature_race, self.anim.id, self.number)

        return race_dir.replace("/", os.path.sep)

    def gen_json_dict(self):
        stages = []
        for idx, sanim in enumerate(self.stage_anims):
            stage_num = idx + 1
            anim_id = "{}_A{}_S{}".format(self.anim.id, self.number, stage_num)
            s = {"id": anim_id}
            s.update(self.stage_defaults)
            if stage_num in self.stage_params:
                s.update(self.stage_params[stage_num])

            stages.append(s)

        d = {
            "type": self.type,
            "stages": stages,
        }
        if self.cum is not None:
            d["add_cum"] = self.cum
        if self.creature_race is not None:
            d["race"] = self.creature_race
        return d

    def gen_fnis_lines(self):
        object_arg = ""
        object_suffix = ""
        if self.object_name:
            object_arg = " -o"
            object_suffix = " " + self.object_name

        lines = []
        for idx, sanim in enumerate(self.stage_anims):
            stage_num = idx + 1
            if idx == 0:
                prefix = "s"
            else:
                prefix = "+"

            filename = os.path.basename(sanim)
            line = "{}{} {}_A{}_S{} {}{}".format(
                    prefix, object_arg, self.anim.id, self.number, stage_num,
                    filename, object_suffix)
            lines.append(line)

        return lines

    def error(self, msg, *args, **kwargs):
        if args or kwargs:
            msg = msg.format(*args, **kwargs)
        self.anim.error("actor {}: {}", self.number, msg)

    def warning(self, msg, *args, **kwargs):
        if args or kwargs:
            msg = msg.format(*args, **kwargs)
        print("warning: actor {}: {}", self.number, msg)


def _parse_stage_params(stage_params, valid_args, on_error):
    if not stage_params:
        return {}

    parsed = {}
    for sp in stage_params:
        if not isinstance(sp, Stage):
            on_error("expected a Stage() object")
            continue
        stage_info = _parse_stage_args(sp.kwargs, valid_args, on_error)
        if not stage_info:
            # This is just a sanity check.  There's no point specifying
            # Stage() with no arguments other than a number.
            on_error("empty stage parameters for stage {}", sp.number)
        parsed[sp.number] = stage_info
        if sp.kwargs:
            on_error("unsupported arguments: {}", ", ".join(kwargs.keys()))

    return parsed


def _parse_stage_args(kwargs, valid_args, on_error):
    d = {}
    for name, type in valid_args.items():
        if name not in kwargs:
            continue
        value = kwargs.pop(name)
        if type == float:
            # Also allow integers in float fields
            allowed_types = (float, int)
        else:
            allowed_types = type
        if not isinstance(value, allowed_types):
            on_error("invalid value for stage param {!r}: "
                    "got {!r}, expected a {}",
                    name, value, type.__name__)
        d[name] = value
    return d


def _preformat_json_for_diff(data):
    # Replace the animation list with a map of anim_id --> anim_info.
    # This makes the JSON diff output much nicer to read when an animation is
    # added or removed.  Rather than showing diff info for everything being
    # shifted up or down, this causes us to show info only for the
    # added/removed animations.
    result = data.copy()
    anim_map = {}
    for anim in data["animations"]:
        anim_map[anim["id"]] = anim
    result["animations"] = anim_map
    return result


def _format_json_diff(old, new):
    lines = []

    def do_diff(ov, nv, path=""):
        if ov == nv:
           return
        if isinstance(ov, dict) and isinstance(nv, dict):
            print_dict_diff(ov, nv, path)
        elif isinstance(ov, list) and isinstance(nv, list):
            print_list_diff(ov, nv, path)
        else:
            lines.append("{}: {!r} vs {!r}".format(path, ov, nv))

    import itertools
    def print_list_diff(od, nd, path=""):
        for idx, (ov, nv) in enumerate(itertools.zip_longest(od, nd)):
            v_path = "{}[{}]".format(path, idx)
            do_diff(ov, nv, v_path)

    def print_dict_diff(od, nd, path=""):
        for k, ov in od.items():
            nv = nd.get(k)
            if path:
                v_path = "{}.{}".format(path, k)
            else:
                v_path = k
            do_diff(ov, nv, v_path)

        for k, nv in nd.items():
            if k in od:
                continue
            if path:
                v_path = "{}.{}".format(path, k)
            else:
                v_path = k
            do_diff(None, nv, v_path)

    do_diff(old, new)
    return lines


class NoDataDirError(Exception):
    def __init__(self, path):
        msg = "cannot find data directory from {}".format(path)
        super().__init__(msg)
        self.path = path


def is_data_dir(path):
    src_dir = os.path.join(path, "SLAnims", "source")
    if os.path.isdir(src_dir):
        return True


def get_data_dir(path):
    cur_path = os.path.abspath(path)
    while True:
        if is_data_dir(cur_path):
            return cur_path
        parent = os.path.dirname(cur_path)
        if cur_path == parent:
            raise NoDataDirError(path)
        cur_path = parent


def find_data_dir():
    # try in the current directory first
    search_list = [
        os.getcwd(),
        os.path.dirname(__file__),
    ]
    for path in search_list:
        try:
            return get_data_dir(path)
        except NoDataDirError:
            continue

    raise Exception("unable to find Skyrim Data/ directory")


#
# GUI handling
#
# We use tkinter simply because it's shipped with Python by default.
# It looks like crap, but users won't need to install any additional packages.
#

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import tkinter.scrolledtext


class GUI(object):
    def __init__(self, master, prefs_path):
        self.master = master
        self.prefs_path = prefs_path

        self.first_focus = True
        self.master.bind("<FocusIn>", self.on_focus)

        # TODO: It would be nice to save the window size in the prefs,
        # and start with the size loaded from prefs.
        self.prefs = self._load_prefs()

        self.data_dir = tkinter.StringVar()
        dd = self.prefs.get("data_dir")
        if not dd:
            dd = find_data_dir()
        self.data_dir.set(dd)

        self.categories = []
        self._init_window()
        self._load_categories()

    def _init_window(self):
        self.master.title("SexLab Animation Loader")

        frame = tkinter.Frame(self.master)
        frame.pack(side=tkinter.TOP, fill=tkinter.BOTH)
        label = tkinter.Label(frame, text="Data directory:",
                              justify=tkinter.LEFT)
        label.pack(side=tkinter.LEFT, fill=tkinter.X)
        data_dir_entry = tkinter.Entry(frame, textvariable=self.data_dir)
        data_dir_entry.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        self.browse = tkinter.Button(frame, text="Browse",
                                     command=self.on_browse)
        self.browse.pack(side=tkinter.LEFT)

        # The category frame
        frame = tkinter.Frame(self.master)
        frame.pack(side=tkinter.TOP, fill=tkinter.X)
        label = tkinter.Label(frame, text="Categories:", justify=tkinter.LEFT)
        label.pack(side=tkinter.LEFT, fill=tkinter.X)
        frame = tkinter.Frame()
        frame.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)
        scroll = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL)
        self.cat_list = tkinter.Listbox(frame, height=5,
                                        exportselection=0,
                                        yscrollcommand=scroll.set)
        self.cat_list.bind("<<ListboxSelect>>", self.on_cat_select)
        self.cat_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        scroll.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        scroll.config(command=self.cat_list.yview)

        # The animation frame
        frame = tkinter.Frame(self.master)
        frame.pack(side=tkinter.TOP, fill=tkinter.X)
        label = tkinter.Label(frame, text="Animations:", justify=tkinter.LEFT)
        label.pack(side=tkinter.LEFT, fill=tkinter.X)
        frame = tkinter.Frame()
        frame.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)
        scroll = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL)
        self.anim_list = tkinter.Listbox(frame, height=10,
                                         exportselection=0,
                                         yscrollcommand=scroll.set)
        self.anim_list.bind("<<ListboxSelect>>", self.on_anim_select)
        self.anim_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        scroll.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        scroll.config(command=self.anim_list.yview)

        # The log frame
        frame = tkinter.Frame(self.master)
        frame.pack(side=tkinter.TOP, fill=tkinter.X)
        label = tkinter.Label(frame, text="Log:", justify=tkinter.LEFT)
        label.pack(side=tkinter.LEFT, fill=tkinter.X)
        frame = tkinter.Frame()
        frame.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)
        scroll = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL)
        scrollx = tkinter.Scrollbar(frame, orient=tkinter.HORIZONTAL)
        self.log = tkinter.Listbox(frame, width=80, height=10,
                                   xscrollcommand=scrollx.set,
                                   yscrollcommand=scroll.set)
        self.log.config(font="Courier 10")
        scrollx.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.log.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        scroll.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        scroll.config(command=self.log.yview)
        scrollx.config(command=self.log.xview)

        frame = tkinter.Frame(self.master)
        frame.pack(side=tkinter.TOP, fill=tkinter.X, pady=5)
        pad = tkinter.Frame(frame)
        pad.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.reload = tkinter.Button(frame, text="Reload",
                                     command=self.on_reload)
        self.reload.pack(side=tkinter.LEFT, padx=5)
        self.build_all = tkinter.Button(frame, text="Build All Categories",
                                        command=self.on_build_all)
        self.build_all.pack(side=tkinter.LEFT, padx=5)
        self.build_one = tkinter.Button(frame, text="Build Category",
                                        command=self.on_build_one,
                                        state=tkinter.DISABLED)
        self.build_one.pack(side=tkinter.LEFT, padx=5)
        self.quit = tkinter.Button(frame, text="Exit", command=frame.quit)
        self.quit.pack(side=tkinter.LEFT, padx=5)
        pad = tkinter.Frame(frame)
        pad.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)

    def on_focus(self, event):
        if event.widget != self.master:
            return
        # on_focus() will be called once when the window is initially drawn.
        # Don't bother reloading the data then.
        if self.first_focus:
            self.first_focus = False
            return

        # Reload the JSON data whenever the main window gets focus again.
        # This just makes things easier when switching back and forth
        # between a text editor working on the sources and the generator: the
        # generator will automatically reload the most recent changes from the
        # editor.
        self._load_categories()

    def on_browse(self):
        dd = self.data_dir.get()
        result = tkinter.filedialog.askdirectory(initialdir=dd)
        if not result:
            return

        # tkinter appears to always return POSIX style paths, even on Windows.
        # Convert it back to to the native path format.
        result = os.path.sep.join(result.split("/"))

        self.data_dir.set(result)
        self._load_categories()
        if not self.categories:
            msg = "No categories found in {}".format(dd)
            tkinter.messagebox.showwarning(title="Warning", message=msg)
        else:
            # Update the preferences whenever a valid-looking directory
            # is selected.
            self.prefs["data_dir"] = result
            self._save_prefs()

    def _selection_info(self):
        # Selection is a tuple of selected elements,
        # which in our case should always be just 1, or possibly 0
        cat_sel = self.cat_list.curselection()
        if not cat_sel:
            return None, None
        cat = self.categories[cat_sel[0]]

        anim_sel = self.anim_list.curselection()
        if not anim_sel:
            return cat, None
        anim = cat.anims[anim_sel[0]]
        return cat, anim

    def on_cat_select(self, event):
        self.anim_list.selection_clear(0, tkinter.END)
        self._clear_log()
        cat, anim = self._selection_info()
        if cat is None:
            self.build_one.config(state=tkinter.DISABLED)
            return

        self._select_cat(cat)

    def _select_cat(self, cat):
        self._log("=== Category Info: {} ===", cat.name)
        for error in cat.errors:
            self._log(str(error))
        for anim in cat.anims:
            if anim.errors:
                self._log("Errors in \"{}\"", anim.name)

        self.anim_list.delete(0, tkinter.END)
        for anim in cat.anims:
            msg = anim.name
            if anim.errors:
                msg += "  (HAS ERRORS)"
            self.anim_list.insert(tkinter.END, msg)

        if cat.errors or cat.anim_errors:
            self.build_one.config(state=tkinter.DISABLED)
            return

        self.build_one.config(state=tkinter.NORMAL)

        if cat.json == cat.old_json:
            self._log("JSON output up-to-date: {}", cat.relpath(cat.json_path))
        elif not cat.old_json:
            self._log("JSON needs to be generated: {}",
                      cat.relpath(cat.json_path))
        else:
            self._log("JSON needs to be regenerated: {}",
                      cat.relpath(cat.json_path))

            # Munge the JSON so the diff is easier to read.
            # Replace animation indices with animation IDs
            old_json = _preformat_json_for_diff(cat.old_json)
            new_json = _preformat_json_for_diff(cat.json)

            lines = _format_json_diff(old_json, new_json)
            for l in lines:
                self._log("  " + l)

        if not cat.fnis_changed:
            self._log("All FNIS lists up-to-date:")
        else:
            self._log("{} FNIS list(s) need rebuilding", len(cat.fnis_changed))
        for path in sorted(cat.fnis_info):
            if path in cat.fnis_changed:
                self._log("- Needs update: {}", cat.relpath(path))
            else:
                self._log("- Up-to-date:   {}", cat.relpath(path))

    def on_anim_select(self, event):
        self._clear_log()
        cat, anim = self._selection_info()
        if cat is None:
            return

        if cat.errors or anim.errors:
            self._log("=== Errors ===")

        for error in cat.errors:
            self._log(str(error))
        for error in anim.errors:
            self._log(str(error))

        if cat.errors or anim.errors:
            return

        self._log("=== Animation Status: {} ===", anim.name)

        fnis_status = None
        for actor in anim.actors:
            fnis_path = actor.get_fnis_list_path()
            fnis_mod_info = cat.fnis_changed.get(fnis_path)
            if fnis_mod_info is None:
                # This FNIS file had no modifications
                continue
            old_info, new_info = fnis_mod_info
            if anim.id not in old_info[0]:
                fnis_status = "new"
                break
            if old_info[0][anim.id] != new_info[0][anim.id]:
                fnis_status = "modified"
                break

        self._add_anim_json_status_log(cat, anim)

        if fnis_status == "new":
            self._log("Not yet present in FNIS list, needs rebuild")
        elif fnis_status == "modified":
            self._log("FNIS list info has changed and needs to be rebuilt")
        else:
            self._log("FNIS list info for this animation is up-to-date")

    def _add_anim_json_status_log(self, cat, anim):
        if not cat.old_json or not cat.old_json.get("animations"):
            self._log("Not yet present in JSON file, needs rebuild")
            return

        old_json_anim = None
        for a in cat.old_json["animations"]:
            if a.get("id") == anim.id:
                old_json_anim = a
                break
        if old_json_anim is None:
            self._log("Not yet present in JSON file, needs rebuild")
            return

        new_json_anim = None
        for a in cat.json["animations"]:
            if a.get("id") == anim.id:
                new_json_anim = a
                break

        if new_json_anim != old_json_anim:
            self._log("Animation modified and JSON data needs rebuild")
        else:
            self._log("JSON data for this animation is up-to-date")

    def on_reload(self):
        self._load_categories()

    def on_build_all(self):
        cat, anim = self._selection_info()

        # Reload categories before doing anything, just in case the
        # source files have changed.
        self._load_categories()

        modified_files = []
        self._clear_log()
        self._log("=== Build Logs ===")
        try:
            for cat in self.categories:
                cat_modified = self._build_category(cat)
                modified_files.extend(cat_modified)
        except:
            self._log_exc()

        self._check_fnis_changed(modified_files)

        # Redisplay the categories
        self._redisplay_categories(clear_log=False)

    def on_build_one(self):
        cat, anim = self._selection_info()
        if cat is None:
            # This shouldn't happen since we have the button disabled
            msg = "No category selected"
            tkinter.messagebox.showwarning(title="Warning", message=msg)
            return

        # Reload the category, just in case the source has changed
        cat_idx = self.cat_list.curselection()[0]
        cat = Category.load(cat.src_path)
        self.categories[cat_idx] = cat

        if cat.errors or cat.anim_errors:
            self._redisplay_categories(cat.name)
            msg = "Errors found in updated source"
            tkinter.messagebox.showerror(title="Error", message=msg)
            return

        self._clear_log()
        self._log("=== Build Logs ===")
        # Save the new build data
        try:
            modified_files = self._build_category(cat)
        except:
            self._log_exc()

        self._check_fnis_changed(modified_files)
        self._redisplay_categories(cat.name, clear_log=False)

    def _check_fnis_changed(self, modified_files):
        fnis_changed = False
        for path in modified_files:
            if path.lower().endswith('.txt'):
                fnis_changed = True
                break
        if fnis_changed:
            self._log("!! Remember to re-run GenerateFNISforModders.exe !!")

    def _log_exc(self):
        for line in traceback.format_exception(*sys.exc_info()):
            self._log(line.rstrip())

    def _log(self, msg, *args, **kwargs):
        if args or kwargs:
            msg = msg.format(*args, **kwargs)
        for line in msg.splitlines():
            self.log.insert(tkinter.END, line)

    def _clear_log(self):
        self.log.delete(0, tkinter.END)

    def _build_category(self, cat):
        if cat.errors or cat.anim_errors:
            self._log("{}: skipping due to source errors", cat.name)
            return []

        modified_files = []
        if cat.json == cat.old_json:
            self._log("{}: JSON already up-to-date", cat.name)
        else:
            cat.save_json()
            modified_files.append(cat.json_path)
            self._log("{}: updated JSON file {}", cat.name, cat.json_path)

        if not cat.fnis_changed:
            self._log("{}: FNIS lists already up-to-date", cat.name)
        for path in sorted(cat.fnis_changed.keys()):
            cat.save_fnis(path)
            modified_files.append(path)
            self._log("{}: updated FNIS list {}", cat.name, path)

        return modified_files

    def _load_categories(self):
        old_cat, old_anim = self._selection_info()
        old_cat_name = old_cat.name if old_cat else None

        self.cat_list.delete(0, tkinter.END)
        self.anim_list.delete(0, tkinter.END)
        self._clear_log()

        src_dir = os.path.join(self.data_dir.get(), "SLAnims", "source")
        self.categories = []
        try:
            dir_entries = os.listdir(src_dir)
        except OSError:
            return

        new_cat_idx = None
        for entry in dir_entries:
            if not _is_source_file(entry):
                continue

            entry_path = os.path.join(src_dir, entry)
            cat = Category.load(entry_path)
            if cat.is_example:
                continue
            if cat.name == old_cat_name:
                new_cat_idx = len(self.categories)
            self.categories.append(cat)
            self._display_cat(cat)

        # If there is only one category, select it.
        if new_cat_idx is None and len(self.categories) == 1:
            new_cat_idx = 0

        if new_cat_idx != None:
            self.cat_list.selection_set(new_cat_idx)
            self._select_cat(self.categories[new_cat_idx])

    def _redisplay_categories(self, old_cat_name=None, clear_log=True):
        self.cat_list.delete(0, tkinter.END)
        self.anim_list.delete(0, tkinter.END)
        if clear_log:
            self._clear_log()

        new_cat_idx = None
        for idx, cat in enumerate(self.categories):
            self._display_cat(cat)
            if cat.name == old_cat_name:
                new_cat_idx = idx

        # If there is only one category, select it.
        if new_cat_idx is None and len(self.categories) == 1:
            new_cat_idx = 0

        if new_cat_idx != None:
            self.cat_list.selection_set(new_cat_idx)
            self._select_cat(self.categories[new_cat_idx])

    def _display_cat(self, cat):
        entry = cat.name
        if cat.errors:
            entry += "  (HAS ERRORS)"
        if cat.anim_errors:
            s = "" if cat.anim_errors == 1 else "S"
            entry += "  ({} ANIMATION ERROR{})".format(cat.anim_errors, s)

        if not cat.errors and not cat.anim_errors:
            if cat.json != cat.old_json or cat.fnis_changed:
                entry += "  (NEEDS BUILD)"
        self.cat_list.insert(tkinter.END, entry)

    def _load_prefs(self):
        try:
            with open(self.prefs_path, "r") as f:
                return json.load(f)
        except:
            return {}

    def _save_prefs(self):
        d = json.dumps(self.prefs, indent=True, sort_keys=True,
                       ensure_ascii=False)
        with open(self.prefs_path, "w") as f:
            f.write(d)


def _is_source_file(entry):
    if entry.endswith(".py"):
        return True

    # Allow files ending in ".txt" too.
    # This is to avoid confusion if users have configured ".py" files to be
    # executed with python by default.  Users will generally want to edit these
    # files, not run them directly with python.
    if entry.endswith(".txt"):
        return True
    return False


def process_dir(path):
    path = get_data_dir(path)
    src_dir = os.path.join(path, "SLAnims", "source")
    for entry in os.listdir(src_dir):
        if not _is_source_file(entry):
            continue

        entry_path = os.path.join(src_dir, entry)
        print("Processing {}".format(entry))
        cat = Category.load(entry_path)
        if cat.is_example:
            print("skipping example entry")
            continue
        cat.save_all()


def process_path(path):
    cat = Category.load(path)
    cat.save_all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--data-dir",
                    help="The path to the Skyrim Data/ directory, "
                    "or to a mod directory")
    ap.add_argument("-p", "--preferences",
                    help="The path to the preferences file")
    ap.add_argument("paths", nargs="*",
                    help="Specific source files to process")
    args = ap.parse_args()

    prefs_path = args.preferences
    if prefs_path is None:
        prefs_path = os.path.expanduser(r"~\AppData\Local\Skyrim"
                                        r"\SLAnimLoader.json")

    if args.paths:
        for p in args.paths:
            if os.path.isdir(p):
                process_dir(p)
            else:
                process_file(p)
        return

    root = tkinter.Tk()
    GUI(root, prefs_path)
    root.mainloop()


if __name__ == "__main__":
    main()
