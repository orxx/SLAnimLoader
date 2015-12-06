Scriptname slalOnLoad extends ReferenceAlias  

event OnInit()
    (GetOwningQuest() as slalLoader).OnLoad()
endEvent

event OnPlayerLoadGame()
    (GetOwningQuest() as slalLoader).OnLoad()
endEvent
