SexLab Animation Loader
=======================

SLAnimLoader registers custom animations with SexLab.  It reads information
about the animations from Data\\SLAnims\\json\\

This makes it possible to add new animations without needing to edit any mods
or do any scripting.  This also makes it easy to change animation tags, actor
positions, sounds, mouth positions, etc.


Source Files vs JSON
--------------------

While you can edit the JSON files manually in your favorite text editor, this
isn't recommended.  Hand editing these fields is tedious, and it's easy to get
the syntax slightly wrong.  If you have a syntax error, Skyrim will fail to
load the file and won't give you any error information about what line of your
file was wrong.

Therefore SLAnimLoader supports building the JSON data from source files in
Data\\SLAnims\\source\\.

Data\\SLAnims\\source\\Example.txt contains a brief overview of the syntax of
the source files.  The Example.txt file itself will be automatically skipped by
SLAnimGenerate, since it contains the line "is\_example = True".  You can
remove this line if you want to play around with it in SLAnimGenerate, but
there aren't any actual animation files associated with it, so no animation
stages will be found.  If you copy Example.txt to start building your own
animation pack, be sure to remove the "is\_example = True" setting.


Setting up your Source file and Animation files
-----------------------------------------------

You will generally want to group all of your animations into a single category.
Pick a name for your category, and create a source file with that name.  For
example, Data\\SLAnims\\source\\YourCategory.txt

Now put your \*.hkx animation files into into the directory
meshes\\actors\\characters\\animations\\YourCategory\\.  Animations for
creatures should go into the appropriate creature directory (e.g.
meshes\\actors\\draugr instead of meshes\\actors\\characters).

You will have one \*.hkx for each stage of each actor.  Your files should be
named AnimName_A1_S1.hkx for the 1st actors 1st stage, AnimName_A2_S3.hkx for
the 2nd actor's 3rd stage, etc.

In the YourCategory.txt source file, add a new Animation() statement for your
animation.  The "id" field must match the name of your animation files.  e.g.,
put id="Foo" if your files are Foo_A1_S1.hkx, Foo_A1_S2.hkx, etc.


Building the JSON Data
----------------------

Run Data\\SLAnims\\SLAnimGenerate.pyw to process your source file.  This will
generate a corresponding JSON file under Data\\SLAnims\\json, and will also
generate FNIS lists in each of your animation directories (one for each race).

Any time a FNIS list file is updated, you need to re-run
GenerateFNISforModders.exe to process the list file.  After you have
processed all of the FNIS lists, then re-run GenerateFNISforUsers.exe.

Once this is done everything should be ready to start Skyrim and register your
animations.


Tweaking Parameters
-------------------

Once you have loaded your animation into Skyrim, you may notice that the actor
positions aren't quite right, the sound is wrong, or some other minor issue.
You can tweak most simple parameters like this without having to quit skyrim.

Simply modify your category source file, and then build it with
SLAnimGenerate.pyw.  You can do this while Skyrim is still running.

Next, go into the SLAnimLoader MCM menu, and in the "General Options" section,
click "Reapply JSON Settings".  This will update the settings for all
SLAnimLoader animations that were already registered with Skyrim.


Rebuilding the SexLab Animation Registry
----------------------------------------

Whenever the SexLab animation registry is rebuilt, SLAnimLoader will
re-register it's enabled animations.  To unregister all SLAnimLoader
animations, click the "Disable All" button in the "General Options" page of the
MCM, then rebuild the SexLab animation registry.
