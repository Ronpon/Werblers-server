"""
Equip Card Generator — composites a portrait onto the Equip Card Template,
adds text overlays for item name, type, strength bonus, and a centred blurb.

Equip cards follow the same compositing approach as Minion cards:
  - Portrait is placed behind the template frame
  - Top frame: type label (left) and strength bonus (right)
  - Name banner: item name centred with a gentle arc
  - Bottom text area: description blurb, centred, italic

Usage:
    python generate_equip_card.py                   # generate ALL equip cards
    python generate_equip_card.py sweet_bandana     # generate one by key
"""

from __future__ import annotations

import numpy as np
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ═══════════════════════════════════════════════════════════════════════════
# EQUIP CARD DATA — add new items here
# ═══════════════════════════════════════════════════════════════════════════

EQUIP_CARDS: dict[str, dict] = {
    "sweet_bandana": {
        "name": "Sweet Bandana",
        "type": "Helmet",
        "strength": "+2",
        "portrait": "Bandana.png",
        "output": "Sweet Bandana Card.png",
        "blurb": "Lookin' good!",
    },
    "colander": {
        "name": "Colander",
        "type": "Helmet",
        "strength": "+1",
        "portrait": "Colander.png",
        "output": "Colander Card.png",
        "blurb": "You just look dumb.",
    },
    "propeller_hat": {
        "name": "Propeller Hat",
        "type": "Helmet",
        "strength": "+2",
        "portrait": "Propellor Hat.png",
        "output": "Propeller Hat Card.png",
        "blurb": "It's fun, but not the most effective.",
    },
    "leather_cap": {
        "name": "Leather Cap",
        "type": "Helmet",
        "strength": "+3",
        "portrait": "Leather Cap.png",
        "output": "Leather Cap Card.png",
        "blurb": "Fairly functional.",
    },
    "miners_helmet": {
        "name": "Miner's Helmet",
        "type": "Helmet",
        "strength": "+3",
        "portrait": "Miner's Helmet.png",
        "output": "Miner's Helmet Card.png",
        "blurb": "It has a snazzy light!",
    },
    "baseball_cap": {
        "name": "Baseball Cap",
        "type": "Helmet",
        "strength": "+2",
        "portrait": "Baseball Cap.png",
        "output": "Baseball Cap Card.png",
        "blurb": "Please don't wear it backwards.",
    },
    "nazi_helmet": {
        "name": "Nazi Helmet",
        "type": "Helmet",
        "strength": "+3",
        "portrait": "Nazi Helmet.png",
        "output": "Nazi Helmet Card.png",
        "blurb": "Is it worth it? Really?",
    },
    "lupine_helm": {
        "name": "Lupine Helm",
        "type": "Helmet",
        "strength": "+4",
        "portrait": "Lupine Helm.png",
        "output": "Lupine Helm Card.png",
        "blurb": "It's a wolf skull. From a dead wolf. Wicked.",
    },
    "paper_bag": {
        "name": "Paper Bag",
        "type": "Helmet",
        "strength": "+1",
        "portrait": "Paper Bag.png",
        "output": "Paper Bag Card.png",
        "blurb": "Ability: Enemies cannot see your gender or class.",
    },
    "football_helmet": {
        "name": "Football Helmet",
        "type": "Helmet",
        "strength": "+5",
        "portrait": "Football Helmet.png",
        "output": "Football Helmet Card.png",
        "blurb": "Won't prevent concussion.",
    },
    "squires_helm": {
        "name": "Squire's Helm",
        "type": "Helmet",
        "strength": "+4",
        "portrait": "Squire's Helm.png",
        "output": "Squire's Helm Card.png",
        "blurb": "It's like the Knight's Helm\u2026 but slightly worse.",
    },
    "swiss_guard_helmet": {
        "name": "Swiss Guard's Helmet",
        "type": "Helmet",
        "strength": "+5",
        "portrait": "Swiss Guard's Helmet.png",
        "output": "Swiss Guard's Helmet Card.png",
        "blurb": "Feathers? How fancy!",
    },
    "crown_of_the_colossus": {
        "name": "Crown of the Colossus",
        "type": "Helmet",
        "strength": "+7",
        "portrait": "Crown of the Colossus.png",
        "output": "Crown of the Colossus Card.png",
        "blurb": "It's a bit bulky.",
    },
    "astronaut_helmet": {
        "name": "Astronaut Helmet",
        "type": "Helmet",
        "strength": "+6",
        "portrait": "Astronaut Helmet.png",
        "output": "Astronaut Helmet Card.png",
        "blurb": "You're not the man they think you are at home.",
    },
    "horned_helm": {
        "name": "Horned Helm",
        "type": "Helmet",
        "strength": "+7",
        "portrait": "Horned Helm.png",
        "output": "Horned Helm Card.png",
        "blurb": "They look so cool in Skyrim.",
    },
    "knights_helm": {
        "name": "Knight's Helm",
        "type": "Helmet",
        "strength": "+7",
        "portrait": "Knight's Helm.png",
        "output": "Knight's Helm Card.png",
        "blurb": "So noble. So powerful. So\u2026 hard to see\u2026",
    },
    "crown_of_thorns": {
        "name": "Crown of Thorns",
        "type": "Helmet",
        "strength": "+1",
        "portrait": "Crown of Thorns.png",
        "output": "Crown of Thorns Card.png",
        "blurb": "Ability: +1 Str. for every Trait you have.",
    },
    "face_mask": {
        "name": "Face Mask",
        "type": "Helmet",
        "strength": "+5",
        "portrait": "Face Mask.png",
        "output": "Face Mask Card.png",
        "blurb": "Ability: If you come across a Coronavirus, win automatically, and add five +1 Str. tokens to this card.",
    },
    "gimp_mask": {
        "name": "Gimp Mask",
        "type": "Helmet",
        "strength": "?",
        "portrait": "Gimp Mask.png",
        "output": "Gimp Mask Card.png",
        "blurb": "Bring it out.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# CHEST ARMOUR CARD DATA — add new chest items here
# ═══════════════════════════════════════════════════════════════════════════

CHEST_CARDS: dict[str, dict] = {
    "gunshot_wound": {
        "name": "Gunshot Wound",
        "type": "Chest",
        "strength": "-3",
        "portrait": "Gunshot Wound.png",
        "output": "Gunshot Wound Card.png",
        "blurb": "It's oozing.",
    },
    "bulletproof_vest": {
        "name": "Bulletproof Vest",
        "type": "Chest",
        "strength": "+8",
        "portrait": "Bulletproof Vest.png",
        "output": "Bulletproof Vest Card.png",
        "blurb": "TBD",
    },
    "sweater_vest": {
        "name": "Sweater Vest",
        "type": "Chest",
        "strength": "+1",
        "portrait": "Sweater Vest.png",
        "output": "Sweater Vest Card.png",
        "blurb": "Could it BE any less helpful?",
    },
    "peasants_robes": {
        "name": "Peasant's Robes",
        "type": "Chest",
        "strength": "+1",
        "portrait": "Peasant Robes.png",
        "output": "Peasant's Robes Card.png",
        "blurb": "Found in every damn closet you search through.",
    },
    "puffy_shirt": {
        "name": "Puffy Shirt",
        "type": "Chest",
        "strength": "+2",
        "portrait": "Puffy Shirt.png",
        "output": "Puffy Shirt Card.png",
        "blurb": "Wear it on The Today Show!",
    },
    "junk_mail": {
        "name": "Junk Mail",
        "type": "Chest",
        "strength": "+2",
        "portrait": "Junk Mail.png",
        "output": "Junk Mail Card.png",
        "blurb": "Nobody likes it.",
    },
    "leather_armour": {
        "name": "Leather Armour",
        "type": "Chest",
        "strength": "+3",
        "portrait": "Leather Armour.png",
        "output": "Leather Armour Card.png",
        "blurb": "Protects, and smells great.",
    },
    "fan_mail": {
        "name": "Fan Mail",
        "type": "Chest",
        "strength": "+3",
        "portrait": "Fan Mail.png",
        "output": "Fan Mail Card.png",
        "blurb": "For the famous adventurer.",
    },
    "bionic_arms": {
        "name": "Bionic Arms",
        "type": "Chest",
        "strength": "+1",
        "portrait": "Bionic Arms.png",
        "output": "Bionic Arms Card.png",
        "blurb": "Ability: You have 2 extra arms for the purposes of equipping weapons.",
    },
    "iron_armour": {
        "name": "Iron Armour",
        "type": "Chest",
        "strength": "+4",
        "portrait": "Iron Armour.png",
        "output": "Iron Armour Card.png",
        "blurb": "Boring, but effective.",
    },
    "barbarian_armour": {
        "name": "Barbarian Armour",
        "type": "Chest",
        "strength": "+3",
        "portrait": "Barbarian Armour.png",
        "output": "Barbarian Armour Card.png",
        "blurb": "Ability: If you have a two-handed weapon equipped, this gives you +7 Str. instead of +3.",
    },
    "3d_printed_armour": {
        "name": "3D-Printed Armour",
        "type": "Chest",
        "strength": "+5",
        "portrait": "3D-Printed Armour.png",
        "output": "3D-Printed Armour Card.png",
        "blurb": "Convenient, and surprisingly durable.",
    },
    "steel_plate_armour": {
        "name": "Steel Plate Armour",
        "type": "Chest",
        "strength": "+6",
        "portrait": "Steel Plate Armour.png",
        "output": "Steel Plate Armour Card.png",
        "blurb": "What can I say? It's good armour. Just not that funny.",
    },
    "chain_mail": {
        "name": "Chain Mail",
        "type": "Chest",
        "strength": "+6",
        "portrait": "Chain Mail.png",
        "output": "Chain Mail Card.png",
        "blurb": "Ability: You may send this card to an opponent to draw a Tier 3 Item card.",
    },
    "wizards_robes": {
        "name": "Wizard's Robes",
        "type": "Chest",
        "strength": "+1",
        "portrait": "Wizard's Robes.png",
        "output": "Wizard's Robes Card.png",
        "blurb": "Ability: For every Trait your character possesses, add one +1 Str. token to this card.",
    },
    "padded_doublet_of_light": {
        "name": "Padded Doublet of Light",
        "type": "Chest",
        "strength": "+7",
        "portrait": "Padded Doublet of Light.png",
        "output": "Padded Doublet of Light Card.png",
        "blurb": "Ability: +3 Str. against demons and skeletons.",
    },
    "mithril_chain_vest": {
        "name": "Mithril Chain Vest",
        "type": "Chest",
        "strength": "+8",
        "portrait": "Mithril Chain Vest.png",
        "output": "Mithril Chain Vest Card.png",
        "blurb": "It's a bit small\u2026",
    },
    "dragonscale_chestplate": {
        "name": "Dragonscale Chestplate",
        "type": "Chest",
        "strength": "+8",
        "portrait": "Dragonscale Chestplate.png",
        "output": "Dragonscale Chestplate Card.png",
        "blurb": "Tested for weak spots.",
    },
    "black_box_chestplate": {
        "name": "Chestplate Made of What the Black Box is Made of",
        "type": "Chest",
        "strength": "+8",
        "portrait": "Black Box Armour.png",
        "output": "Black Box Chestplate Card.png",
        "blurb": "They finally did it!",
    },
    "rekt": {
        "name": "Rekt",
        "type": "Chest",
        "strength": "X",
        "portrait": "Rekt.png",
        "output": "Rekt Card.png",
        "blurb": "Ability: This card blocks your Chest slot. You cannot equip Chest armour.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# LEG / FOOTGEAR CARD DATA — add new footgear items here
# ═══════════════════════════════════════════════════════════════════════════

LEG_CARDS: dict[str, dict] = {
    "flip_flops": {
        "name": "Flip Flops",
        "type": "Footgear",
        "strength": "+1",
        "portrait": "Flip Flops.png",
        "output": "Flip Flops Card.png",
        "blurb": "They keep falling off.",
    },
    "sandals": {
        "name": "Sandals",
        "type": "Footgear",
        "strength": "+1",
        "portrait": "Sandals.png",
        "output": "Sandals Card.png",
        "blurb": "Not much defence but at least they stay on.",
    },
    "pumped_up_kicks": {
        "name": "Pumped up Kicks",
        "type": "Footgear",
        "strength": "+2",
        "portrait": "Pumped up Kicks.png",
        "output": "Pumped up Kicks Card.png",
        "blurb": "So bouncy!",
    },
    "rubber_boots": {
        "name": "Rubber Boots",
        "type": "Footgear",
        "strength": "+2",
        "portrait": "Rubber Boots.png",
        "output": "Rubber Boots Card.png",
        "blurb": "Splish Splash!",
    },
    "wheelies": {
        "name": "Wheelies",
        "type": "Footgear",
        "strength": "+2",
        "portrait": "Wheelies.png",
        "output": "Wheelies Card.png",
        "blurb": "Ability: At the start of your movement phase, you may reuse your last played card's value instead of playing a new card.",
    },
    "soccer_cleats": {
        "name": "Soccer Cleats",
        "type": "Footgear",
        "strength": "+3",
        "portrait": "Soccer Cleats.png",
        "output": "Soccer Cleats Card.png",
        "blurb": "Kicks that grip!",
    },
    "pointy_shoes": {
        "name": "Pointy Shoes",
        "type": "Footgear",
        "strength": "+4",
        "portrait": "Pointy Shoes.png",
        "output": "Pointy Shoes Card.png",
        "blurb": "You can poke people with 'em!",
    },
    "boots_of_agility": {
        "name": "Boots of Agility",
        "type": "Footgear",
        "strength": "+1",
        "portrait": "Boots of Agility.png",
        "output": "Boots of Agility Card.png",
        "blurb": "Ability: When playing a movement card, you may add +1 to its value.",
    },
    "boots_of_rooting": {
        "name": "Boots of Rooting",
        "type": "Footgear",
        "strength": "+5",
        "portrait": "Boots of Rooting.png",
        "output": "Boots of Rooting Card.png",
        "blurb": "Ability: You are immune to any curse that causes you to move board position.",
    },
    "hermes_shoes": {
        "name": "Hermes' Shoes",
        "type": "Footgear",
        "strength": "+5",
        "portrait": "Hermes' Shoes.png",
        "output": "Hermes' Shoes Card.png",
        "blurb": "Ability: When playing a movement card, you may treat 1's and 2's as 4's.",
    },
    "homelanders_heels": {
        "name": "Homelander's Heels",
        "type": "Footgear",
        "strength": "+5",
        "portrait": "Homelander's Heels.png",
        "output": "Homelander's Heels Card.png",
        "blurb": "He's actually 5'11\".",
    },
    "steel_greaves": {
        "name": "Steel Greaves",
        "type": "Footgear",
        "strength": "+6",
        "portrait": "Steel Greaves.png",
        "output": "Steel Greaves Card.png",
        "blurb": "Stronger than Iron Greaves.",
    },
    "dragonskin_boots": {
        "name": "Dragonskin Boots",
        "type": "Footgear",
        "strength": "+7",
        "portrait": "Dragonskin boots.png",
        "output": "Dragonskin Boots Card.png",
        "blurb": "Great defence, terrible odour.",
    },
    "boots_of_streaking": {
        "name": "Boots of Streaking",
        "type": "Footgear",
        "strength": "+7",
        "portrait": "Boots of Streaking.png",
        "output": "Boots of Streaking Card.png",
        "blurb": "Ability: If you have no other equipment, this card grants you +20 instead of +7.",
    },
    "armoured_jordans": {
        "name": "Armoured Jordans",
        "type": "Footgear",
        "strength": "+8",
        "portrait": "Armoured Jordans.png",
        "output": "Armoured Jordans Card.png",
        "blurb": "Fly like a heavily-armoured eagle.",
    },
    "dancing_shoes": {
        "name": "Dancing Shoes",
        "type": "Footgear",
        "strength": "+1",
        "portrait": "Dancing Shoes.png",
        "output": "Dancing Shoes Card.png",
        "blurb": "Ability: Cannot be discarded unless the Can't Stop the Music! curse is lifted.",
    },
    "iron_greaves": {
        "name": "Iron Greaves",
        "type": "Footgear",
        "strength": "+4",
        "portrait": "Iron Greaves.png",
        "output": "Iron Greaves Card.png",
        "blurb": "Solid and dependable.",
    },
    "steel_toed_boots": {
        "name": "Steel-Toed Boots",
        "type": "Footgear",
        "strength": "+3",
        "portrait": "Steel-Toed Boots.png",
        "output": "Steel-Toed Boots Card.png",
        "blurb": "OSHA approved.",
    },
    "hiking_boots": {
        "name": "Hiking Boots",
        "type": "Footgear",
        "strength": "+2",
        "portrait": "Hiking Boots.png",
        "output": "Hiking Boots Card.png",
        "blurb": "Great ankle support.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# WEAPON CARD DATA — add new weapons here
# ═══════════════════════════════════════════════════════════════════════════

WEAPON_CARDS: dict[str, dict] = {
    "spork": {
        "name": "Spork",
        "type": "1H Weapon",
        "strength": "+1",
        "portrait": "Spork.png",
        "output": "Spork Card.png",
        "blurb": "Great for eating stew, not great against monsters.",
    },
    "rusty_blade": {
        "name": "Rusty Blade",
        "type": "1H Weapon",
        "strength": "+2",
        "portrait": "Rusty Sword.png",
        "output": "Rusty Blade Card.png",
        "blurb": "It\u2019s past its prime. (Yes, that\u2019s proper grammar)",
    },
    "pot_lid": {
        "name": "Pot Lid",
        "type": "1H Weapon",
        "strength": "+1",
        "portrait": "Pot Lid.png",
        "output": "Pot Lid Card.png",
        "blurb": "Better than nothing\u2026",
    },
    "rat_basher": {
        "name": "Rat Basher",
        "type": "1H Weapon",
        "strength": "+3",
        "portrait": "Rat Basher.png",
        "output": "Rat Basher Card.png",
        "blurb": "Ability: Automatically win battles against rats.",
    },
    "big_ol_hammer": {
        "name": "Big Ol' Hammer",
        "type": "2H Weapon",
        "strength": "+4",
        "portrait": "Big ol' Hammer.png",
        "output": "Big Ol' Hammer Card.png",
        "blurb": "It\u2019s really heavy.",
    },
    "steak_knife": {
        "name": "Steak Knife",
        "type": "1H Weapon",
        "strength": "+2",
        "portrait": "Steak Knife.png",
        "output": "Steak Knife Card.png",
        "blurb": "At least it\u2019s serrated\u2026",
    },
    "pointed_stick": {
        "name": "Poin-ted Stick",
        "type": "1H Weapon",
        "strength": "+2",
        "portrait": "Pointed Stick.png",
        "output": "Poin-ted Stick Card.png",
        "blurb": "Hopefully your opponent only trained against fruit!",
    },
    "mirror_shield": {
        "name": "Mirror Shield",
        "type": "1H Weapon",
        "strength": "+2",
        "portrait": "Mirror Shield.png",
        "output": "Mirror Shield Card.png",
        "blurb": "Sounds impressive, but come on, it\u2019s made of glass.",
    },
    "cool_hwip": {
        "name": "Cool Hwip",
        "type": "1H Weapon",
        "strength": "+5",
        "portrait": "Cool whip.png",
        "output": "Cool Hwip Card.png",
        "blurb": "Why are you saying it like that?",
    },
    "sweeneys_razor": {
        "name": "Sweeney's Razor",
        "type": "1H Weapon",
        "strength": "+4",
        "portrait": "Sweeney's Razor.png",
        "output": "Sweeney's Razor Card.png",
        "blurb": "Time to make some pies\u2026",
    },
    "long_poking_device": {
        "name": "Long Poking Device",
        "type": "2H Weapon",
        "strength": "+3",
        "portrait": "Giant poking device.png",
        "output": "Long Poking Device Card.png",
        "blurb": "Great for poking naked guys.",
    },
    "barbarian_sword": {
        "name": "Barbarian Sword",
        "type": "1H Weapon",
        "strength": "+5",
        "portrait": "Barbarian Sword.png",
        "output": "Barbarian Sword Card.png",
        "blurb": "Ability: If you have no chest or head armour, this gives +10 Str. instead of +5.",
    },
    "nocappins_scimitar": {
        "name": "No\u2019Cappin\u2019s Scimitar",
        "type": "1H Weapon",
        "strength": "+6",
        "portrait": "No'Cappin's Scimitar.png",
        "output": "No'Cappin's Scimitar Card.png",
        "blurb": "Ability: If you have 2 copies of this equipped, they have +8 attack instead of +6.",
    },
    "freeze_ray": {
        "name": "Freeze Ray",
        "type": "2H Weapon",
        "strength": "+2",
        "portrait": "Freeze Ray.png",
        "output": "Freeze Ray Card.png",
        "blurb": "Ability: When drawing a Monster card, you may discard one card to freeze it and receive no Trait or Curse.",
    },
    "rapier_of_taltos": {
        "name": "Rapier of Taltos",
        "type": "1H Weapon",
        "strength": "+7",
        "portrait": "Rapier of Taltos.png",
        "output": "Rapier of Taltos Card.png",
        "blurb": "Perfect for ganking Dragaerans.",
    },
    "claymore_of_freedom": {
        "name": "Claymore of Freedom",
        "type": "2H Weapon",
        "strength": "+11",
        "portrait": "Claymore of Freedom.png",
        "output": "Claymore of Freedom Card.png",
        "blurb": "They\u2019ll never take it.",
    },
    "transmogrifier": {
        "name": "Transmogrifier",
        "type": "1H Weapon",
        "strength": "+0",
        "portrait": "Transmogrifier.png",
        "output": "Transmogrifier Card.png",
        "blurb": "Ability: When drawing a monster card, you may choose to put it at the bottom of the deck and draw a new one of the same level.",
    },
    "tower_shield": {
        "name": "Tower Shield",
        "type": "1H Weapon",
        "strength": "+6",
        "portrait": "Tower Shield.png",
        "output": "Tower Shield Card.png",
        "blurb": "It\u2019s tall and blocks things.",
    },
    "patriotic_shield": {
        "name": "Patriotic Shield",
        "type": "1H Weapon",
        "strength": "+8",
        "portrait": "Patriotic Shield.png",
        "output": "Patriotic Shield Card.png",
        "blurb": "Don\u2019t throw it; it doesn\u2019t bounce.",
    },
    "motha_flippin_machine_gun": {
        "name": "Motha-flippin' Machine Gun",
        "type": "2H Weapon",
        "strength": "+12",
        "portrait": "Motha-flippin' Machine Gun.png",
        "output": "Motha-flippin' Machine Gun Card.png",
        "blurb": "Well that\u2019s just unfair.",
    },
    "flaming_claymore": {
        "name": "Flaming Claymore",
        "type": "2H Weapon",
        "strength": "+12",
        "portrait": "Flaming Claymore.png",
        "output": "Flaming Claymore Card.png",
        "blurb": "\u266b This sword is on fire! \u266b",
    },
    "inconveniently_large_sword": {
        "name": "Inconveniently Large Sword",
        "type": "4H Weapon",
        "strength": "+25",
        "portrait": "Inconveniently Large Sword.png",
        "output": "Inconveniently Large Sword Card.png",
        "blurb": "You probably can\u2019t lift it.",
    },
    "mistress_sword": {
        "name": "Mistress Sword",
        "type": "1H Weapon",
        "strength": "+8",
        "portrait": "Mistress Sword.png",
        "output": "Mistress Sword Card.png",
        "blurb": "For when the princess needs to save herself.",
    },
    "ball_and_chain": {
        "name": "Ball and Chain",
        "type": "1H Weapon",
        "strength": "+5",
        "portrait": "Ball and Chain.png",
        "output": "Ball and Chain Card.png",
        "blurb": "Get Rekt.",
    },
    "power_driver": {
        "name": "Power Driver",
        "type": "2H Weapon",
        "strength": "+8",
        "portrait": "Power Driver.png",
        "output": "Power Driver Card.png",
        "blurb": "Great for fending off scorned wives.",
    },
    "bloody_stump": {
        "name": "Bloody Stump",
        "type": "1H Weapon",
        "strength": "-3",
        "portrait": "Bloody Stump.png",
        "output": "Bloody Stump Card.png",
        "blurb": "Ow.",
    },
    "giants_short_sword": {
        "name": "Giant's Short Sword",
        "type": "2H Weapon",
        "strength": "+10",
        "portrait": "Giant's Short Sword.png",
        "output": "Giant's Short Sword Card.png",
        "blurb": "It\u2019s still pretty damn big.",
    },
    "plasma_blaster": {
        "name": "Plasma Blaster",
        "type": "2H Weapon",
        "strength": "+14",
        "portrait": "Plasma Blaster.png",
        "output": "Plasma Blaster Card.png",
        "blurb": "Donate plasma today!",
    },
    "devils_guitar": {
        "name": "Devil's Guitar",
        "type": "2H Weapon",
        "strength": "+13",
        "portrait": "Devil's Guitar.png",
        "output": "Devil's Guitar Card.png",
        "blurb": "Violins are so pass\u00e9.",
    },
    "mages_gauntlet": {
        "name": "Mage's Gauntlet",
        "type": "1H Weapon",
        "strength": "+5",
        "portrait": "Mage's Gauntlet.png",
        "output": "Mage's Gauntlet Card.png",
        "blurb": "Ability: At any time on your turn, you may discard one Trait card and add one +1 Str. token to this card.",
    },
    "spear_head": {
        "name": "Spear Head",
        "type": "1H Weapon",
        "strength": "+3",
        "portrait": "Spear Head.png",
        "output": "Spear Head Card.png",
        "blurb": "Not super useful without a handle\u2026",
    },
    "steel_katar": {
        "name": "Steel Katar",
        "type": "1H Weapon",
        "strength": "+4",
        "portrait": "Steel Katar.png",
        "output": "Steel Katar Card.png",
        "blurb": "Makes me think of Diablo.",
    },
    "caped_longsword": {
        "name": "Caped Longsword",
        "type": "1H Weapon",
        "strength": "+5",
        "portrait": "Caped Longsword.png",
        "output": "Caped Longsword Card.png",
        "blurb": "Seems inconvenient, but it sure looks classy.",
    },
    "rubber_chicken": {
        "name": "Rubber Chicken",
        "type": "1H Weapon",
        "strength": "+1",
        "portrait": "Rubber Chicken.png",
        "output": "Rubber Chicken Card.png",
        "blurb": "Don\u2019t complain, 1 Str. is GENEROUS.",
    },
    "kamikaze_gun": {
        "name": "Kamikaze Gun",
        "type": "1H Weapon",
        "strength": "+8",
        "portrait": "Kamikaze Gun.png",
        "output": "Kamikaze Gun Card.png",
        "blurb": "Ability: If you lose a battle, you may discard one trait to avoid the curse.",
    },
    "laser_rifle": {
        "name": "Laser Rifle",
        "type": "2H Weapon",
        "strength": "+16",
        "portrait": "Laser Rifle.png",
        "output": "Laser Rifle Card.png",
        "blurb": "It shoots lasers!",
    },
    "alien_rifle": {
        "name": "Alien Rifle",
        "type": "2H Weapon",
        "strength": "+17",
        "portrait": "Alien Rifle.png",
        "output": "Alien Rifle Card.png",
        "blurb": "Doesn\u2019t fit your hand right, but it packs a punch.",
    },
    "bugger_blaster": {
        "name": "Bugger Blaster",
        "type": "1H Weapon",
        "strength": "+10",
        "portrait": "Bugger Blaster.png",
        "output": "Bugger Blaster Card.png",
        "blurb": "Are you sure the Buggers aren\u2019t just misunderstood?",
    },
    "adaptable_blade": {
        "name": "Adaptable Blade",
        "type": "1H Weapon",
        "strength": "?",
        "portrait": "Adaptable Blade.png",
        "output": "Adaptable Blade Card.png",
        "blurb": "Ability: If used one-handed, this has +4 Str. If used two-handed, this has +8 Str.",
    },
    "power_driver": {
        "name": "Power Driver",
        "type": "2H Weapon",
        "strength": "+10",
        "portrait": "Power Driver.png",
        "output": "Power Driver Card.png",
        "blurb": "Great for fending off scorned wives.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════
HEAD_ARMOUR_DIR  = Path("Images/Items/Head Armour")
PORTRAITS_DIR    = HEAD_ARMOUR_DIR / "Head Armour Portraits"
FINISHED_DIR     = HEAD_ARMOUR_DIR / "Head Armour Finished Cards"
TEMPLATE_PATH    = HEAD_ARMOUR_DIR / "Equip card Template.png"

CHEST_ARMOUR_DIR    = Path("Images/Items/Chest Armour")
CHEST_PORTRAITS_DIR = CHEST_ARMOUR_DIR / "Chest Armour Portraits"
CHEST_FINISHED_DIR  = CHEST_ARMOUR_DIR / "Chest Armour Finished Cards"

LEG_ARMOUR_DIR    = Path("Images/Items/Leg Armour")
LEG_PORTRAITS_DIR = LEG_ARMOUR_DIR / "Leg Armour Portraits"
LEG_FINISHED_DIR  = LEG_ARMOUR_DIR / "Leg Armour Finished Cards"

WEAPONS_DIR          = Path("Images/Items/Weapons")
WEAPON_PORTRAITS_DIR = WEAPONS_DIR / "Weapon Portraits"
WEAPON_FINISHED_DIR  = WEAPONS_DIR / "Weapon Finished Cards"


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS  (matches the Equip card template)
# ═══════════════════════════════════════════════════════════════════════════
CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP    = 230
PORTRAIT_WINDOW_BOTTOM = 1033
PORTRAIT_WINDOW_LEFT   = 48
PORTRAIT_WINDOW_RIGHT  = 1008

# Top frame
TYPE_LABEL_POS = (160, 55)   # type label in the left band
STRENGTH_POS   = (910, 62)   # strength value in the right flap

# Name banner
NAME_BANNER_TOP    = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area
TEXT_AREA_TOP    = 1070
TEXT_AREA_LEFT   = 142
TEXT_AREA_RIGHT  = 882
TEXT_AREA_BOTTOM = 1470
TEXT_LINE_HEIGHT_FACTOR = 1.30


# ═══════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════
FONT_DIR = Path(r"C:\Windows\Fonts")


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by filename, falling back to Arial."""
    search_dirs = [FONT_DIR, Path(".")]
    for d in search_dirs:
        for ext in (".ttf", ".otf"):
            p = d / name.replace(".ttf", ext).replace(".otf", ext)
            if p.exists():
                return ImageFont.truetype(str(p), size)
        p = d / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype(str(FONT_DIR / "arial.ttf"), size)


font_type_label    = _load_font("Cinzel-Black.ttf", 42)
font_strength      = _load_font("Cinzel-Black.ttf", 56)
font_name          = _load_font("Almendra-Bold.ttf", 64)
font_blurb         = _load_font("MedievalSharp-Oblique.ttf", 36)
font_blurb_upright = _load_font("MedievalSharp.ttf", 36)
font_blurb_bold    = _load_font("MedievalSharp-Bold.ttf", 36)


# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM      = (255, 240, 200)
COLOR_DARK       = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)


# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def draw_curved_text(
    canvas: Image.Image,
    text: str,
    y_center: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    arc_depth: int = 8,
    x_center: int = CARD_W // 2,
) -> None:
    """Draw text warped along a gentle parabolic arc."""
    tmp = ImageDraw.Draw(canvas)
    bbox = tmp.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_y = abs(arc_depth) + 10
    strip_w = tw + 20
    strip_h = th + pad_y * 2
    strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    text_x = (strip_w - tw) // 2 - bbox[0]
    text_y = pad_y - bbox[1]
    sd.text((text_x, text_y), text, font=font, fill=fill)

    arr = np.array(strip)
    out = np.zeros_like(arr)
    half_w = strip_w / 2.0

    for col in range(strip_w):
        t = (col - half_w) / half_w if half_w else 0.0
        shift = int(round(arc_depth * (1.0 - t * t)))
        if shift >= 0:
            if shift < strip_h:
                out[shift:, col] = arr[:strip_h - shift, col]
        else:
            s = -shift
            if s < strip_h:
                out[:strip_h - s, col] = arr[s:, col]

    warped = Image.fromarray(out, "RGBA")
    paste_x = x_center - strip_w // 2
    paste_y = y_center - strip_h // 2
    canvas.alpha_composite(warped, (paste_x, paste_y))


def _pixel_wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap text using actual pixel measurements."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textlength(trial, font=font) <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(
    item: dict,
    portraits_dir: Path = PORTRAITS_DIR,
    finished_dir: Path = FINISHED_DIR,
    template_path: Path = TEMPLATE_PATH,
    force: bool = False,
) -> Path:
    """Generate a single equip card and return the output path."""
    portrait_path = portraits_dir / item["portrait"]
    output_path   = finished_dir  / item["output"]

    if not force and output_path.exists():
        print(f"  skip (already exists): {output_path.name}")
        return output_path

    if not portrait_path.exists():
        print(f"  SKIP — portrait not found: {portrait_path}")
        return output_path

    template = Image.open(template_path).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    # Brighten template slightly for readability
    tpl_rgb = template.convert("RGB")
    tpl_bright = ImageEnhance.Brightness(tpl_rgb).enhance(1.08)
    tpl_bright_rgba = tpl_bright.convert("RGBA")
    tpl_bright_rgba.putalpha(template.getchannel("A"))
    template = tpl_bright_rgba

    # --- Portrait placement ---
    pw, ph = portrait.size
    window_w = PORTRAIT_WINDOW_RIGHT - PORTRAIT_WINDOW_LEFT
    window_h = PORTRAIT_WINDOW_BOTTOM - PORTRAIT_WINDOW_TOP

    scale = max(window_w / pw, window_h / ph)
    new_w = int(pw * scale)
    new_h = int(ph * scale)
    portrait_resized = portrait.resize((new_w, new_h), Image.LANCZOS)

    px = PORTRAIT_WINDOW_LEFT + (window_w - new_w) // 2
    py = PORTRAIT_WINDOW_TOP

    canvas = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    canvas.paste(portrait_resized, (px, py))
    canvas = Image.alpha_composite(canvas, template)

    draw = ImageDraw.Draw(canvas)
    text_width = TEXT_AREA_RIGHT - TEXT_AREA_LEFT

    # ------------------------------------------------------------------
    # TOP FRAME — type label and strength bonus
    # ------------------------------------------------------------------
    draw.text(TYPE_LABEL_POS, item["type"].upper(),
              font=font_type_label, fill=COLOR_CREAM)

    str_text = item["strength"]
    s_bbox = draw.textbbox((0, 0), str_text, font=font_strength)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text((STRENGTH_POS[0] - s_w // 2, STRENGTH_POS[1]),
              str_text, font=font_strength, fill=COLOR_DARK)

    # ------------------------------------------------------------------
    # NAME BANNER — centred with gentle arc
    # ------------------------------------------------------------------
    name_font = font_name
    NAME_BANNER_HPAD = 60
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP

    name_bbox = draw.textbbox((0, 0), item["name"], font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]
    cur_name_size = name_font.size

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        name_font = _load_font("Almendra-Bold.ttf", cur_name_size)
        name_bbox = draw.textbbox((0, 0), item["name"], font=name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    name_y = NAME_BANNER_TOP + (banner_h - name_h) // 2 + 8
    name_y = max(NAME_BANNER_TOP, name_y)
    arc = int(round(-6 - 0.0125 * max(0, name_w - 350)))

    name_y_center = name_y + name_h // 2
    draw_curved_text(canvas, item["name"], name_y_center, name_font,
                     COLOR_DARK, arc_depth=arc)
    draw = ImageDraw.Draw(canvas)  # refresh after alpha_composite

    # ------------------------------------------------------------------
    # BOTTOM TEXT AREA — blurb, italic, centred H+V
    # ------------------------------------------------------------------
    blurb_text = item["blurb"]

    is_ability = blurb_text.startswith("Ability:")
    blurb_font = font_blurb_upright if is_ability else font_blurb
    ABILITY_PREFIX = "Ability:"
    lines = _pixel_wrap(draw, blurb_text, blurb_font, text_width)
    total_h = 0
    line_heights: list[int] = []
    for line in lines:
        if line.startswith(ABILITY_PREFIX):
            b1 = draw.textbbox((0, 0), ABILITY_PREFIX, font=font_blurb_bold)
            b2 = draw.textbbox((0, 0), line[len(ABILITY_PREFIX):], font=blurb_font)
            lh = int(max(b1[3] - b1[1], b2[3] - b2[1]) * TEXT_LINE_HEIGHT_FACTOR)
        else:
            bbox = draw.textbbox((0, 0), line, font=blurb_font)
            lh = int((bbox[3] - bbox[1]) * TEXT_LINE_HEIGHT_FACTOR)
        line_heights.append(lh)
        total_h += lh

    STAR_PAD = 30
    star_text = "*  *  *"
    star_font = _load_font("MedievalSharp.ttf", 28)
    star_bbox = draw.textbbox((0, 0), star_text, font=star_font)
    star_h = star_bbox[3] - star_bbox[1]

    block_h = star_h + STAR_PAD + total_h + STAR_PAD + star_h
    area_h = TEXT_AREA_BOTTOM - TEXT_AREA_TOP
    block_top = TEXT_AREA_TOP + (area_h - block_h) // 2 - 3

    star_w = star_bbox[2] - star_bbox[0]
    star_x = TEXT_AREA_LEFT + (text_width - star_w) // 2
    draw.text((star_x, block_top), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    y = block_top + star_h + STAR_PAD

    for i, line in enumerate(lines):
        if line.startswith(ABILITY_PREFIX):
            suffix = line[len(ABILITY_PREFIX):]
            pfx_bbox = draw.textbbox((0, 0), ABILITY_PREFIX, font=font_blurb_bold)
            sfx_bbox = draw.textbbox((0, 0), suffix, font=blurb_font)
            pfx_w = pfx_bbox[2] - pfx_bbox[0]
            sfx_w = sfx_bbox[2] - sfx_bbox[0]
            total_w = pfx_w + sfx_w
            x = TEXT_AREA_LEFT + (text_width - total_w) // 2
            draw.text((x, y), ABILITY_PREFIX, font=font_blurb_bold, fill=COLOR_DARK_BROWN)
            draw.text((x + pfx_w, y), suffix, font=blurb_font, fill=COLOR_DARK_BROWN)
        else:
            bbox = draw.textbbox((0, 0), line, font=blurb_font)
            lw = bbox[2] - bbox[0]
            x = TEXT_AREA_LEFT + (text_width - lw) // 2
            draw.text((x, y), line, font=blurb_font, fill=COLOR_DARK_BROWN)
        y += line_heights[i]

    draw.text((star_x, y + STAR_PAD), star_text, font=star_font, fill=COLOR_DARK_BROWN)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------
    canvas.save(str(output_path), "PNG")
    print(f"  -> {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    raw_args = sys.argv[1:]
    force = "--all" in raw_args
    args = [a.lower() for a in raw_args if a != "--all"]
    all_cards = {**EQUIP_CARDS, **CHEST_CARDS, **LEG_CARDS, **WEAPON_CARDS}

    if not args:
        print("=== Head Armour Cards ===")
        for key, item in EQUIP_CARDS.items():
            print(f"Generating {item['name']}...")
            generate_card(item, force=force)
        print("\n=== Chest Armour Cards ===")
        for key, item in CHEST_CARDS.items():
            print(f"Generating {item['name']}...")
            generate_card(item, CHEST_PORTRAITS_DIR, CHEST_FINISHED_DIR, force=force)
        print("\n=== Footgear Cards ===")
        for key, item in LEG_CARDS.items():
            print(f"Generating {item['name']}...")
            generate_card(item, LEG_PORTRAITS_DIR, LEG_FINISHED_DIR, force=force)
        print("\n=== Weapon Cards ===")
        for key, item in WEAPON_CARDS.items():
            print(f"Generating {item['name']}...")
            generate_card(item, WEAPON_PORTRAITS_DIR, WEAPON_FINISHED_DIR, force=force)
    else:
        for key in args:
            if key not in all_cards:
                print(f"  Unknown equip card key: '{key}'")
                print(f"  Available: {', '.join(all_cards.keys())}")
                continue
            if key in CHEST_CARDS:
                item = CHEST_CARDS[key]
                print(f"Generating {item['name']}...")
                generate_card(item, CHEST_PORTRAITS_DIR, CHEST_FINISHED_DIR, force=force)
            elif key in LEG_CARDS:
                item = LEG_CARDS[key]
                print(f"Generating {item['name']}...")
                generate_card(item, LEG_PORTRAITS_DIR, LEG_FINISHED_DIR, force=force)
            elif key in WEAPON_CARDS:
                item = WEAPON_CARDS[key]
                print(f"Generating {item['name']}...")
                generate_card(item, WEAPON_PORTRAITS_DIR, WEAPON_FINISHED_DIR, force=force)
            else:
                item = EQUIP_CARDS[key]
                print(f"Generating {item['name']}...")
                generate_card(item, force=force)

    print("Done.")


if __name__ == "__main__":
    main()
