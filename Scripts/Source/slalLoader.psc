Scriptname slalLoader extends slalAnimationFactory

slalMCM Property Config Auto

function verboseMsg(string msg)
    if Config.verboseLogs
        slalData.debugMsg(msg)
    endIf
endFunction

function debugMsg(string msg)
    slalData.debugMsg(msg)
endFunction

function warningMsg(string msg)
    slalData.warningMsg(msg)
endFunction

function OnLoad()
    debugMsg("SLAL: OnLoad")
    RegisterForModEvent("SexLabSlotAnimations", "registerAnimations")
    RegisterForModEvent("SexLabSlotCreatureAnimations", "registerCreatureAnimations")

    ; After any game load, make sure we re-read JSON data the next time it is
    ; needed.  (Don't bother re-reading it now, since we won't actually need it
    ; unless the MCM menu is opened.)
    slalData.unloadData()
endFunction

; Register all enabled animations
bool registeringAnimations
int function registerAnimations()
	if !registeringAnimations
		registeringAnimations = true
		debugMsg("SLAL: registering animations")
		PrepareFactory()

		int enableState = slalData.getEnableState()
		int anims = slalData.getAnimations()
		string animID = JMap.nextKey(anims)
		int numRegistered = 0
		while animID
			if !JMap.hasKey(JMap.getObj(anims, animID), "creature_race") && registerAnimIfEnabled(animID, anims, enableState)
				numRegistered += 1
			endIf

			animID = JMap.nextKey(anims, animID)
		endWhile

		debugMsg("SLAL: finished registering " + numRegistered + " animations")
		registeringAnimations = false
		return numRegistered
	endIf
	return 0
endFunction

bool registeringCreatureAnimations
int function registerCreatureAnimations()
	if !registeringCreatureAnimations
		registeringCreatureAnimations = true
		debugMsg("SLAL: registering animations")
		PrepareFactory()

		int enableState = slalData.getEnableState()
		int anims = slalData.getAnimations()
		string animID = JMap.nextKey(anims)
		int numRegistered = 0
		while animID
			if JMap.hasKey(JMap.getObj(anims, animID), "creature_race") && registerAnimIfEnabled(animID, anims, enableState)
				numRegistered += 1
			endIf

			animID = JMap.nextKey(anims, animID)
		endWhile

		debugMsg("SLAL: finished registering " + numRegistered + " animations")
		registeringCreatureAnimations = false
		return numRegistered
	endIf
	return 0
endFunction

; Register the enabled animations from a specific category
; Other categories are ignored, even if they have enabled but not yet
; registered animations.
int function registerCategoryAnimations(string catName)
    debugMsg("SLAL: registering " + catName + " animations")
    PrepareFactory()

    int enableState = slalData.getEnableState()
    int anims = slalData.getAnimations()
    int catAnims = slalData.getCategoryAnims(catName)
    int numAnims = JArray.count(catAnims)

    int n = 0
    int numRegistered = 0
    while n < numAnims
        string animID = JArray.getStr(catAnims, n)
        if registerAnimIfEnabled(animID, anims, enableState)
            numRegistered += 1
        endIf

        n += 1
    endWhile

    debugMsg("SLAL: finished registering " + numRegistered + " animations")
    return numRegistered
endFunction

function updateJsonSettings()
    int anims = slalData.getAnimations()
    string animID = JMap.nextKey(anims)
    while animID
        sslAnimationSlots animSlots = getSlotsByAnimID(animID)
        int sexlabID = animSlots.FindByRegistrar(animID)
        if sexlabID != -1
            sslBaseAnimation anim = animSlots.GetBySlot(sexlabID)
            anim.Initialize()
            anim.Registry = animId
            anim.Enabled  = true

            InitAnimSlot(animSlots, sexlabID, animId, "OnRegisterAnim")
        endIf

        animID = JMap.nextKey(anims, animID)
    endWhile
endFunction

bool function registerAnimIfEnabled(string animID, int anims, int enableState)
    bool enabled = JMap.getInt(enableState, animID) as bool
    if !enabled
        return false
    endIf

    int animInfo = JMap.getObj(anims, animID)
    sslAnimationSlots animSlots = getSlots(animInfo)
    return RegisterAnimationCB(animSlots, animID, "OnRegisterAnim")
endFunction

; Get the correct sslAnimationSlots to use for the specified animation
sslAnimationSlots function getSlots(int animInfo)
    bool isCreature = JMap.hasKey(animInfo, "creature_race")
    if isCreature
        return CreatureSlots
    endIf
    return Slots
endFunction

sslAnimationSlots function getSlotsByAnimID(string animID)
    int animInfo = slalData.getAnimInfo(animID)
    return getSlots(animInfo)
endFunction

bool function isRegistered(string animID)
    sslAnimationSlots animSlots = getSlotsByAnimID(animID)
    return animSlots.IsRegistered(animID)
endFunction

function OnRegisterAnim(int id, string animID)
    verboseMsg("registering animation: " + animID)

    int animInfo = slalData.getAnimInfo(animID)

    sslBaseAnimation anim = CreateInSlots(getSlots(animInfo), id)
    anim.Name = JMap.getStr(animInfo, "name")
    anim.SoundFX = getSound(animInfo)
    verboseMsg("  anim = " + anim)
    verboseMsg("  Name = " + anim.Name)
    verboseMsg("  SoundFX = " + anim.SoundFX)

    int actors = JMap.getObj(animInfo, "actors")
    int numActors = JArray.count(actors)
    int n = 0
    while n < numActors
        int actorInfo = JArray.getObj(actors, n)
        addActorInfo(anim, animInfo, actorInfo)
        n += 1
    endWhile

    int stages = JMap.getObj(animInfo, "stages")
    int numStages = JArray.count(stages)
    n = 0
    while n < numStages
        int stageInfo = JArray.getObj(stages, n)
        addStageInfo(anim, stageInfo)

        n += 1
    endWhile

    int AnimOffsets = JMap.getObj(animInfo, "animoffsets")
    int numAnimOffsets = JArray.count(AnimOffsets)
    n = 0
    while n < numAnimOffsets
        int AnimOffsetInfo = JArray.getObj(AnimOffsets, n)
        addAnimOffsetsInfo(anim, AnimOffsetInfo)

        n += 1
    endWhile

    string tags = JMap.getStr(animInfo, "tags")
    verboseMsg("  Tags = " + anim.SoundFX)
    anim.SetTags(tags)

    anim.Save(id)
endFunction

function addActorInfo(sslBaseAnimation anim, int animInfo, int actorInfo)
    int actorID = addActorPosition(anim, animInfo, actorInfo)

    int stages = JMap.getObj(actorInfo, "stages")
    int numStages = JArray.count(stages)
    int n = 0
    while n < numStages
        int stageInfo = JArray.getObj(stages, n)
        addActorStagePlus(anim, actorID, stageInfo, n+1)
        n += 1
    endWhile
endFunction

function addActorStagePlus(sslBaseAnimation anim, int actorID, int stageInfo, int stage = 0)
	addActorStage(anim, actorID, stageInfo)
	if stage > 0
		int cum = getActorCum(stageInfo)
		if cum != -1
			int cumsrc = JMap.getInt(stageInfo, "cumsrc", -1)
			anim.SetStageCumID(actorID, stage, cum, cumsrc)
		endIf
	endIf
endFunction

function addActorStage(sslBaseAnimation anim, int actorID, int stageInfo)
    string eventID = JMap.getStr(stageInfo, "id")
    float forward = JMap.getFlt(stageInfo, "forward")
    float side = JMap.getFlt(stageInfo, "side")
    float up = JMap.getFlt(stageInfo, "up")
    float rotate = JMap.getFlt(stageInfo, "rotate")
    bool silent = JMap.getInt(stageInfo, "silent") as bool
    bool openMouth = JMap.getInt(stageInfo, "open_mouth") as bool
    bool strapOn = JMap.getInt(stageInfo, "strap_on") as bool
    int sos = JMap.getInt(stageInfo, "sos")

    verboseMsg("  + " + anim + ".AddPositionStage(" + actorID + ", " + eventID + ",")
    verboseMsg("        forward=" + forward + ", side=" + side + ", up=" + up + ", rotate=" + rotate + ",")
    verboseMsg("        silent=" + silent + ", openmouth=" + openmouth + ", strapon=" + strapon + ", sos=" + sos + ")")
    anim.AddPositionStage(actorID, eventID, forward=forward, side=side, up=up, rotate=rotate, silent=silent, openmouth=openmouth, strapon=strapOn, sos=sos)
endFunction

function addAnimOffsetsInfo(sslBaseAnimation anim, int offsetInfo)
	string Type = JMap.getStr(offsetInfo, "type")
	float Forward = JMap.getFlt(offsetInfo, "forward")
	float Sideward = JMap.getFlt(offsetInfo, "sideward")
	float Upward = JMap.getFlt(offsetInfo, "upward")
	float Rotate = JMap.getFlt(offsetInfo, "rotate")
	if Forward != 0.0 || Sideward != 0.0 || Upward != 0.0 || Rotate != 0.0
		if !Type || Type == "" || Type == "Bed"
			anim.SetBedOffsets(Forward, Sideward, Upward, Rotate)
		elseIf Type == "Furniture"
			anim.SetFurnitureOffsets(Forward, Sideward, Upward, Rotate)
		endIf
	endIf
endFunction

function addStageInfo(sslBaseAnimation anim, int stageInfo)
    int stageNum = JMap.getInt(stageInfo, "number")

    if JMap.hasKey(stageInfo, "sound")
        string soundName = JMap.getStr(stageInfo, "sound")
        verboseMsg("  SetStageSoundFX(" + stageNum + ", " + soundName + ")")
        anim.SetStageSoundFX(stageNum, getSoundByName(soundName))
    endIf
    if JMap.hasKey(stageInfo, "timer")
        float timer = JMap.getFlt(stageInfo, "timer")
        verboseMsg("  SetStageTimer(" + stageNum + ", " + timer + ")")
        anim.SetStageTimer(stageNum, timer)
    endIf
endFunction

Sound function getSound(int animInfo)
    string soundName = JMap.getStr(animInfo, "sound")
    return getSoundByName(soundName)
endFunction

Sound function getSoundByName(string soundName)
    if !soundName || soundName == "none"
        return none
    elseIf soundName == "Squishing"
        return Squishing
    elseIf soundName == "Sucking"
        return Sucking
    elseIf soundName == "SexMix"
        return SexMix
    elseIf soundName == "Squirting"
        return Squirting
    endIf

    warningMsg("unrecognized sound '" + soundName + "'")
    return none
endFunction

int function addActorPosition(sslBaseAnimation anim, int animInfo, int actorInfo)
    string type = JMap.getStr(actorInfo, "type")
    string creatureRace
    int cum

    if type == "Male"
        cum = getActorCum(actorInfo)
        verboseMsg("  AddPosition(Male, addCum=" + cum + ")")
        return anim.AddPosition(Male, addCum=cum)
    elseIf type == "Female"
        cum = getActorCum(actorInfo)
        verboseMsg("  AddPosition(Female, addCum=" + cum + ")")
        return anim.AddPosition(Female, addCum=cum)
    elseIf type == "Creature"
        creatureRace = JMap.getStr(animInfo, "creature_race")
        verboseMsg("  AddCreaturePosition(" + creatureRace + ", Creature)")
        return anim.AddCreaturePosition(creatureRace, Creature)
    elseIf type == "CreatureMale"
        creatureRace = JMap.getStr(actorInfo, "race")
        anim.GenderedCreatures = true
        cum = getActorCum(actorInfo)
        verboseMsg("  AddCreaturePosition(" + creatureRace + ", CreatureMale, addCum=" + cum + ")")
        return anim.AddCreaturePosition(creatureRace, CreatureMale, AddCum=cum)
    elseIf type == "CreatureFemale"
        creatureRace = JMap.getStr(actorInfo, "race")
        anim.GenderedCreatures = true
        cum = getActorCum(actorInfo)
        verboseMsg("  AddCreaturePosition(" + creatureRace + ", CreatureFemale, addCum=" + cum + ")")
        return anim.AddCreaturePosition(creatureRace, CreatureFemale, AddCum=cum)
    endIf

    warningMsg("unrecognized actor type '" + type + "'")
    return anim.AddPosition(Male)
endFunction

int function getActorCum(int actorInfo)
    ; Try the field as an integer first
    int cum = JMap.getInt(actorInfo, "add_cum", -99)
    if cum != -99
        return cum
    endIf

    string name = JMap.getStr(actorInfo, "add_cum")
    if name == "" || name == "none"
        return -1
    elseIf name == "Vaginal"
        return Vaginal
    elseIf name == "Oral"
        return Oral
    elseIf name == "Anal"
        return Anal
    elseIf name == "VaginalOral"
        return VaginalOral
    elseIf name == "VaginalAnal"
        return VaginalAnal
    elseIf name == "OralAnal"
        return OralAnal
    elseIf name == "VaginalOralAnal"
        return VaginalOralAnal
    endIf

    warningMsg("unrecognized add_cum value '" + name + "'")
    return -1
endFunction
