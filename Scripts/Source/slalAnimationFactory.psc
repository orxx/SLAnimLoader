Scriptname slalAnimationFactory extends sslAnimationFactory
;
; This module provides functionality very similar to sslAnimationFactory, but
; tweaked to support the needs of SLAnimLoader.  In particular, it supports:
; - Registering multiple animations with a single callback, whose name does
;   not need to match the animation ID.
; - Registering both character and creature animations in a single script.
;

sslCreatureAnimationSlots property CreatureSlots auto hidden

; Prepare the factory
function PrepareFactory()
    parent.PrepareFactory()
    if !CreatureSlots
        CreatureSlots = Game.GetFormFromFile(0x664FB, "SexLab.esm") as sslCreatureAnimationSlots
    endIf
endFunction

; Similar to sslAnimationFactory.RegisterAnimation(), but accepts an extra
; parameter indicating the name of a callback function to invoke.  If
; specified, this callback will be invoked with the Registrar argument.
; This makes it possible to use a single callback function with many different
; animations.
;
; It also accepts the slots to use as a parameter as well (normal or creature slots).
bool function RegisterAnimationCB(sslAnimationSlots animSlots, string Registrar, string Callback = "")
    ; Get free Animation slot
    int id = animSlots.Register(Registrar)
    if id != -1
        InitAnimSlot(animSlots, id, Registrar, Callback)
    endIf
    return (id != -1)
endFunction

function InitAnimSlot(sslAnimationSlots animSlots, int id, string Registrar, string Callback)
    ; Init slot
    sslBaseAnimation Slot = animSlots.GetBySlot(id)
    Slot.Initialize()
    Slot.Registry = Registrar
    Slot.Enabled  = true
    ; Send load event
    int eid = ModEvent.Create(Registrar)
    ModEvent.PushInt(eid, id)
    if Callback
        RegisterForModEvent(Registrar, Callback)
        ModEvent.PushString(eid, Registrar)
    else
        RegisterForModEvent(Registrar, Registrar)
    endIf
    ModEvent.Send(eid)
endFunction

sslBaseAnimation function CreateInSlots(sslAnimationSlots animSlots, int id)
	sslBaseAnimation Slot = animSlots.GetbySlot(id)
	UnregisterForModEvent(Slot.Registry)
	return Slot
endFunction
