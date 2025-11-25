from AutoComplete import *
from System import Byte
from System.Collections.Generic import List

############################################
# SETTINGS
############################################

runToPet = False
useMagery = True
useMageryHighHP = True   # kept for self logic if you want to expand later
useVet = False
useDiscord = False
discordEverything = False

bandageSerial = None
bandageContainer = Player.Backpack

instrumentSerial = None
instrumentContainer = Player.Backpack

# Mastery disabled via Option A
untargetedMasteryBuffs = []
masteryWatchMana = False

############################################
# PERFORMANCE HELPERS
############################################

lastCombatValue = False
petID = None
petSerial = None

def cachedCombat():
    """Cache combat state for 500ms to avoid spam-intensive mobile scans."""
    global lastCombatValue
    if not Timer.Check("combatRefresh"):
        Timer.Create("combatRefresh", 500)
        lastCombatValue = combatCheck()
    return lastCombatValue

def cachedPet():
    """Refresh pet every 1s instead of every loop."""
    global petID, petSerial
    if not Timer.Check("petRefresh"):
        Timer.Create("petRefresh", 1000)
        petID = Mobiles.FindBySerial(petSerial)
    return petID

############################################
# CORE FUNCTIONS
############################################

def combatCheck():
    combatFilter = Mobiles.Filter()
    combatFilter.RangeMax = 12
    combatFilter.CheckIgnoreObject = True
    combatFilter.Notorieties = List[Byte](bytes([4, 5, 6]))
    combatList = Mobiles.ApplyFilter(combatFilter)
    return bool(combatList)

def masteryBuffCheck():
    # Mastery disabled (Option A)
    return False

def pathFindToPet():
    pet = cachedPet()
    if not pet:
        return
    petCoords = PathFinding.Route()
    petCoords.X = pet.Position.X - 1
    petCoords.Y = pet.Position.Y
    petCoords.DebugMessage = False
    petCoords.StopIfStuck = True
    petCoords.IgnoreMobile = False
    if PathFinding.Go(petCoords):
        return
    petCoords.X = pet.Position.X + 1
    if PathFinding.Go(petCoords):
        return
    petCoords.X = pet.Position.X
    petCoords.Y = pet.Position.Y - 1
    if PathFinding.Go(petCoords):
        return
    petCoords.Y = pet.Position.Y + 1
    PathFinding.Go(petCoords)

def findDiscordTarget():
    discordFilter = Mobiles.Filter()
    discordFilter.RangeMax = 8
    if discordEverything:
        discordFilter.Notorieties = List[Byte](bytes([3, 4, 5, 6]))
    else:
        discordFilter.Notorieties = List[Byte](bytes([4, 5, 6]))
    discordFilter.CheckIgnoreObject = True
    discordFilter.Friend = False
    return Mobiles.ApplyFilter(discordFilter)

def findInstrument():
    global instrumentContainer
    instruments = [0x2805, 0x0E9C, 0x0EB3, 0x0EB2, 0x0EB1, 0x0E9E, 0x0E9D]
    if instrumentSerial:
        instrumentContainer = Items.FindBySerial(instrumentSerial)
    for i in instrumentContainer.Contains:
        if i.ItemID in instruments:
            Target.TargetExecute(i.Serial)
            Journal.Clear()
            Misc.Pause(60)
            return True
    return False

def discordEnemies():
    if not useDiscord:
        return False
    if Timer.Check('skillTimer'):
        return False

    targets = findDiscordTarget()
    mob = Mobiles.Select(targets, 'Next')
    if not mob:
        return False

    Journal.Clear()
    Target.Cancel()
    Player.UseSkill('Discordance')
    Misc.Pause(60)

    if Journal.SearchByType('What instrument shall you play?', 'System'):
        if not findInstrument():
            Target.Cancel()
            Misc.SendMessage('No Instruments!', 1100)
            Misc.Pause(60)
            return False

    Target.WaitForTarget(2000)
    Target.ExecuteTarget(mob)
    Misc.Pause(60)

    if Journal.Search('That creature is already in discord.') and not Journal.Search('That is too far away.'):
        return False

    Timer.Create('skillTimer', 3500)
    return True

############################################
# SAFE CASTING HELPERS (NO GLOBAL SPELLTIMER)
############################################

def safeCast(spellName, targetSerial=None, selfTarget=False, waitMs=2000):
    """
    Safe magery cast:
    - Waits until you're not already casting (no overwrite)
    - Cancels a stuck target cursor
    - Casts, waits for target cursor, then targets pet or self
    - No global spell cooldown; we rely on Player.Casting + loop timing
    """
    if not useMagery:
        return False

    # Don't overwrite a spell currently being cast
    try:
        while Player.Casting:
            Misc.Pause(20)
    except:
        pass

    # Clear stuck target cursor
    if Target.HasTarget:
        Target.Cancel()

    Spells.CastMagery(spellName)

    if Target.WaitForTarget(waitMs):
        if selfTarget or targetSerial is None:
            Target.TargetExecute(Player.Serial)
        else:
            Target.TargetExecute(targetSerial)
    else:
        return False

    # Let the server register the spell
    Misc.Pause(120)
    return True

############################################
# HEALTH / POISON HELPERS
############################################

def getHealthPercent(mob):
    return 100 * mob.Hits / mob.HitsMax if mob and mob.HitsMax > 0 else 0

def getManaPercent():
    return 100 * Player.Mana / Player.ManaMax if Player.ManaMax > 0 else 0

############################################
# CURE LOGIC (SELF & PET)
############################################

def cureSelf():
    """
    CURE ASAP:
    - If poisoned: try Cure first.
    - If still poisoned shortly after, escalate to Arch Cure.
    Throttled with a small timer so it doesn't spam like crazy.
    """
    if not useMagery or not Player.Poisoned:
        return False
    if Timer.Check('cureSelfTimer'):
        return False

    # Try Cure first
    safeCast('Cure', selfTarget=True)
    Misc.Pause(200)

    if Player.Poisoned:
        # Escalate to Arch Cure
        safeCast('Arch Cure', selfTarget=True)

    Timer.Create('cureSelfTimer', 800)
    return True

def curePet(thresholdPercent=90):
    """
    CURE PET ASAP:
    - Use same logic: Cure first, then Arch Cure if still poisoned.
    - Pet must be within 11 tiles.
    """
    pet = cachedPet()
    if not pet or not useMagery:
        return False
    if not pet.Poisoned:
        return False
    if Timer.Check('curePetTimer'):
        return False
    if Player.DistanceTo(pet) > 11:
        return False

    # Try Cure first
    safeCast('Cure', targetSerial=pet.Serial)
    Misc.Pause(200)

    pet = cachedPet()
    if pet and pet.Poisoned:
        # Escalate to Arch Cure
        safeCast('Arch Cure', targetSerial=pet.Serial)

    Timer.Create('curePetTimer', 800)
    return True

############################################
# SELF HEALING (MINI HEAL <30, GH >=30)
############################################

def healSelf(healthPercent):
    """
    Heal Self:
    - Only if health < given percent
    - missing >= 30 HP → Greater Heal
    - 0 < missing < 30 HP → Mini Heal (Heal)
    - Does nothing if poisoned (cureSelf handles that first)
    """
    if not useMagery or Player.Poisoned:
        return False

    currentPercent = getHealthPercent(Player)
    if currentPercent >= healthPercent:
        return False

    missing = Player.HitsMax - Player.Hits
    if missing <= 0:
        return False

    if missing >= 30 and Player.Mana > 15:
        # Greater Heal for big hits
        return safeCast('Greater Heal', selfTarget=True)
    elif missing < 30 and Player.Mana > 10:
        # Mini Heal for small hits only
        return safeCast('Heal', selfTarget=True)

    return False

############################################
# PET HEALING (ONLY GREATER HEAL, BELOW 90%)
############################################

def healPet(thresholdPercent=90):
    """
    Heal Pet:
    - ONLY Greater Heal
    - Start healing when pet HP < thresholdPercent (90%)
    - No mini heals, no top-off behavior beyond this threshold.
    """
    pet = cachedPet()
    if not pet or pet.Hits <= 0:
        return False
    if not useMagery or pet.Poisoned:
        return False  # poison is handled by curePet first
    if Player.DistanceTo(pet) > 11:
        return False

    hpPercent = getHealthPercent(pet)
    if hpPercent >= thresholdPercent:
        return False

    # Only Greater Heal on pet
    return safeCast('Greater Heal', targetSerial=pet.Serial)

############################################
# VETERINARY (UNCHANGED)
############################################

def vetPet(healthPercent):
    pet = cachedPet()
    if not pet or not useVet:
        return False
    if getHealthPercent(pet) < healthPercent or pet.Poisoned:
        if runToPet and Player.DistanceTo(pet) > 2:
            pathFindToPet()
        if Player.DistanceTo(pet) <= 2 and not Player.BuffsExist('Veterinary'):
            bandage = Items.FindByID(0x0E21, 0, bandageContainer.Serial)
            if bandage:
                Items.UseItem(bandage, pet.Serial)
                Misc.Pause(60)
                return True
    return False

############################################
# FIND PET ON STARTUP (LOYALTY RATING)
############################################

def findMyPet():
    innocentFilter = Mobiles.Filter()
    innocentFilter.RangeMax = 20
    innocentFilter.Notorieties = List[Byte](bytes([1, 2]))
    innocentFilter.CheckIgnoreObject = True
    innocentFilter.IsHuman = False

    innocents = Mobiles.ApplyFilter(innocentFilter)
    pets = [m for m in innocents if any("Loyalty Rating:" in p for p in Mobiles.GetPropStringList(m))]
    mine = [p for p in pets if p.CanRename]

    return mine[0] if mine else None

while not petID:
    petID = findMyPet()
    if petID:
        petSerial = petID.Serial
        Player.HeadMessage(65, "Pet located: " + petID.Name)
        Player.HeadMessage(65, "Tamer Script D ready!")
        break
    Player.HeadMessage(1100, "Pet not located — retrying in 5s")
    Misc.Pause(5000)

############################################
# MAIN LOOP — HIGH SPEED, PRIORITY TREE
############################################

while True:
    while not Player.IsGhost:
        cachedPet()
        cachedCombat()

        # PRIORITY:
        # 1) Cures (self then pet) – ASAP
        if cureSelf(): continue
        if curePet(90): continue

        # 2) Self survival at lower HP
        if healSelf(50): continue

        # 3) Pet survival (GH only, <90%)
        if healPet(90): continue

        # 4) Vet if enabled
        if vetPet(50): continue

        # 5) Additional self healing at higher HP thresholds
        if healSelf(80): continue
        if vetPet(90): continue
        if healSelf(90): continue

        # 6) Discord if enabled
        if discordEnemies(): continue

        Misc.Pause(80)  # fast idle pause

    Misc.Pause(800)  # slower pause while dead to save CPU