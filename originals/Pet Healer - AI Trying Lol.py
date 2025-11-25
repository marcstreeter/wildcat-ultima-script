# v.1.2.2 — Optimized Edition (EOF-safe)
# Mastery disabled via Option A (untargetedMasteryBuffs = [])
# Performance improvements implemented

from AutoComplete import *
from System import Byte
from System.Collections.Generic import List

############################################
# SETTINGS
############################################

runToPet = False
useMagery = True
useMageryHighHP = True
useVet = False
useDiscord = False
discordEverything = False

bandageSerial = None
bandageContainer = Player.Backpack

instrumentSerial = None
instrumentContainer = Player.Backpack

# OPTION A (mastery disabled):
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
            Misc.Pause(120)
            return True
    return False

def discordEnemies():
    if not useDiscord or Timer.Check('skillTimer'):
        return False
    targets = findDiscordTarget()
    mob = Mobiles.Select(targets, 'Next')
    if not mob:
        return False
    Journal.Clear()
    Target.Cancel()
    Player.UseSkill('Discordance')
    Misc.Pause(120)
    if Journal.SearchByType('What instrument shall you play?', 'System'):
        if not findInstrument():
            Target.Cancel()
            Misc.SendMessage('No Instruments!', 1100)
            Misc.Pause(120)
            return False
    Target.WaitForTarget(2000)
    Target.ExecuteTarget(mob)
    Misc.Pause(120)
    if Journal.Search('That creature is already in discord.') and not Journal.Search('That is too far away.'):
        return False
    Timer.Create('skillTimer', 3500)
    return True

def cureSelf():
    if useMagery and Player.Poisoned and not Timer.Check('spellTimer') and Player.Mana > 15:
        Spells.CastMagery('Arch Cure')
        Target.WaitForTarget(2000)
        Target.TargetExecute(Player.Serial)
        Misc.Pause(120)
        Timer.Create("spellTimer", 2500)
        return True
    return False

def curePet(healthPercent):
    pet = cachedPet()
    if not pet:
        return False
    if Player.DistanceTo(pet) <= 11 and useMagery and pet.Poisoned and not Timer.Check('spellTimer') and not Player.BuffsExist('Veterinary'):
        if useMageryHighHP or getHealthPercent(pet) < healthPercent:
            Spells.CastMagery('Arch Cure')
            Target.WaitForTarget(2000)
            Target.TargetExecute(pet.Serial)
            Misc.Pause(120)
            Timer.Create("spellTimer", 2500)
            return True
    return False

def healSelf(healthPercent):
    if getHealthPercent(Player) < healthPercent and useMagery and not Timer.Check('spellTimer') and not Player.Poisoned:
        missing = Player.HitsMax - Player.Hits
        if missing > 30 and Player.Mana > 15:
            Spells.CastMagery('Greater Heal')
        elif Player.Mana > 10:
            Spells.CastMagery('Heal')
        else:
            return False
        Target.WaitForTarget(2000)
        Target.TargetExecute(Player.Serial)
        Misc.Pause(120)
        Timer.Create("spellTimer", 2500)
        return True
    return False

def healPet(healthPercent):
    pet = cachedPet()
    if not pet:
        return False
    if Player.DistanceTo(pet) <= 11 and useMagery and not pet.Poisoned and not Timer.Check('spellTimer'):
        if getHealthPercent(pet) < healthPercent or (getHealthPercent(pet) < 80 and useMageryHighHP):
            Spells.CastMagery('Greater Heal')
            Target.WaitForTarget(2000)
            Target.TargetExecute(pet.Serial)
            Misc.Pause(120)
            Timer.Create("spellTimer", 2500)
            return True
    return False

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
                Misc.Pause(120)
                return True
    return False

def getHealthPercent(mob):
    return 100 * mob.Hits / mob.HitsMax if mob else 0

def getManaPercent():
    return 100 * Player.Mana / Player.ManaMax

############################################
# FIND PET ON STARTUP
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
        Player.HeadMessage(65, "Tamer AIO ready!")
        break
    Player.HeadMessage(1100, "Pet not located — retrying in 5s")
    Misc.Pause(5000)

############################################
# MAIN LOOP — HIGH SPEED
############################################

while True:
    while not Player.IsGhost:

        cachedPet()      # refresh every 1s
        cachedCombat()   # refresh every 500ms

        # FAST PRIORITY TREE
        if cureSelf(): continue
        if healSelf(50): continue
        if vetPet(50): continue
        if curePet(50): continue
        if healPet(50): continue
        if healSelf(80): continue
        if vetPet(90): continue
        if healSelf(90): continue
        if discordEnemies(): continue

        Misc.Pause(80)   # fast, safe idle pause

    Misc.Pause(160)