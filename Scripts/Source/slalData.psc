Scriptname slalData Hidden

function debugMsg(string msg) global
    Debug.Trace("SLAL: " + msg)
endFunction

function warningMsg(string msg) global
    Debug.Trace("SLAL warning: " + msg)
endFunction

function errorMsg(string msg) global
    Debug.Trace("SLAL error: " + msg)
    Debug.Notification("SLAL error: " + msg)
endFunction

; Returns a JMap of {Category Name -> JArray of animID strings}
int function getCategories() global
    int categories = JDB.solveObj(".SLAL.categories")
    if categories == 0
        reloadData()
        categories = JDB.solveObj(".SLAL.categories")
    endIf

    return categories
endFunction

; Returns a JArray of animID strings for the specified category
int function getCategoryAnims(string cat) global
    return JMap.getObj(getCategories(), cat)
endFunction

; Returns a JMap of {AnimID -> Animation Info}
int function getAnimations() global
    int anims = JDB.solveObj(".SLAL.animations")
    if anims == 0
        reloadData()
        anims = JDB.solveObj(".SLAL.animations")
    endIf

    return anims
endFunction

; Get the JMap containing the animation info for a given animation ID
int function getAnimInfo(string animID) global
    int anims = getAnimations()
    return JMap.getObj(anims, animID)
endFunction

; Returns a JMap of {animID --> bool}
int function getEnableState() global
    int enableState = JDB.solveObj(".SLAL.enableState")
    if enableState == 0
        enableState = JMap.object()
        JDB.solveObjSetter(".SLAL.enableState", enableState, true)
    endIf

    return enableState
endFunction

; Unload the JSON data
; This makes sure that it will be reloaded the next time is is needed
function unloadData() global
    ; Reset the category and animation data
    ; We intentionally leave enableState as-is, since this is not
    ; loaded from a file on disk.
    JDB.solveObjSetter(".SLAL.categories", 0, true)
    JDB.solveObjSetter(".SLAL.animations", 0, true)
endFunction

int function reloadData() global
    debugMsg("reloading data")
    int data = JValue.readFromDirectory("Data/SLAnims/json", ".json")
    JValue.retain(data)

    int categories = JValue.retain(JMap.object())
    int anims = JValue.retain(JMap.object())

    int catInfo
    int numErrors = 0
    string catName
    string path = JMap.nextKey(data)
    while path
        catInfo = JMap.getObj(data, path)
        numErrors += loadCategory(path, catInfo, categories, anims)
        path = JMap.nextKey(data, path)
    endwhile

    JDB.solveObjSetter(".SLAL.categories", categories, true)
    JDB.solveObjSetter(".SLAL.animations", anims, true)

    ; Release the json objects we retained above.
    ; (We retain them just in case loading the data somehow takes a very long
    ; time, and JContainers expires them before we can put them in the JDB.)
    JValue.release(categories)
    JValue.release(anims)
    JValue.release(data)

    debugMsg("loaded " + JMap.count(categories) + " JSON files")
    debugMsg("found " + numErrors + " animations with errors in the JSON data")
    return numErrors
endFunction

int function loadCategory(string path, int catInfo, int categories, int allAnims) global
    string catName = JMap.getStr(catInfo, "name")
    if catName == ""
        errorMsg("unable to load " + path + ": no name field")
        return 1
    endIf

    int catAnimIDs = JValue.retain(JArray.object())
    int catAnims = JMap.getObj(catInfo, "animations")
    int numAnims = JArray.count(catAnims)
    int n = 0
    int numErrors = 0
    while n < numAnims
        int animInfo = JArray.getObj(catAnims, n)
        if loadAnimation(path, n, animInfo, allAnims)
            string animID = JMap.getStr(animInfo, "id")
            JArray.addStr(catAnimIDs, animID)

            if JMap.getStr(animInfo, "error") != ""
                numErrors += 1
            endIf
        else
            ; Missing ID or name, so we have to completely ignore this animation
            numErrors += 1
        endIf

        n += 1
    endWhile

    JMap.setObj(categories, catName, catAnimIDs)
    JValue.release(catAnimIDs)
    debugMsg("loaded category " + catName + ": " + numAnims + " animations")
    return numErrors
endFunction

bool function loadAnimation(string path, int animIndex, int animInfo, int allAnims) global
    string animID = JMap.getStr(animInfo, "id")
    if !animID
        errorMsg(path + " animation " + animIndex + ": missing id")
        return false
    endIf

    string animName = JMap.getStr(animInfo, "name")
    if !animName
        errorMsg(path + " animation " + animIndex + ": missing name")
        return false
    endIf

    ; The generator script may already include error text
    string error = JMap.getStr(animInfo, "error")
    if !animName
        return true
    endIf

    error = processAnimation(path, animID, animInfo)
    ; As long as we have the name and ID, we still add the animation info
    ; to allAnims, even if an error occurred.  It will still show up in the
    ; configuration menu, but it will be disabled and have error info
    ; attached to it.
    JMap.setStr(animInfo, "error", error)
    JMap.setObj(allAnims, animID, animInfo)
    return true
endFunction

string function addWarning(int animInfo, string warning) global
    string allWarn = JMap.getStr(animInfo, "warning")
    if allWarn
        allWarn += "; " + warning
    else
        allWarn = warning
    endIf
    JMap.setStr(animInfo, "warning", allWarn)
endFunction

string function processAnimation(string path, string animID, int animInfo) global
    int actors = JMap.getObj(animInfo, "actors")
    if actors == 0
        return "missing actors"
    endIf

    int numActors = JArray.count(actors)
    if numActors < 1
        return "must have at least 1 actor"
    endIf

    ; TODO: make sure all actors have the same number of stages

    ; TODO: Make sure creature_race is set (and is valid)
    ; if any of the actors are a creature type

    ; TODO: check to see if the sound is valid
    ; TODO: make sure other fields have valid values

    return ""
endFunction
