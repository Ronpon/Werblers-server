"""
Monster Card Generator — composites a portrait onto the Monster Card Template,
adds text overlays for monster name, type, strength, description, trait, and curse.

The layout has:
  - Top frame: "MONSTER" label (left) and Strength value (right)
  - Name banner: monster name centred on parchment
  - Portrait: placed behind the template frame
  - Bottom text area:
      • Description/blurb in italics, centred
      • Two-column layout: Trait (left) | divider | Curse (right)

Usage:
    python generate_monster_card.py                     # generate ALL monsters
    python generate_monster_card.py nose_goblin         # generate one by key
"""

from __future__ import annotations

import numpy as np
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ═══════════════════════════════════════════════════════════════════════════
# MONSTER DATA — add new monsters here
# ═══════════════════════════════════════════════════════════════════════════

MONSTERS: dict[str, dict] = {
    "nose_goblin": {
        "name": "Nose Goblin",
        "type": "Monster",
        "strength": "+1",
        "level": 1,
        "portrait": "Nose Goblin.png",
        "output": "Nose Goblin Card.png",
        "description": "Should we tell him?",
        "trait": {
            "name": "Calloused",
            "text": "While wearing no Head armour, you have +3 Str.",
        },
        "curse": {
            "name": "Wait, You Lost to THIS?",
            "text": (
                "But It Has One Strength! ONE! "
                "Just… hang your head in shame…"
            ),
        },
    },

    "attack_turtle": {
        "name": "Attack Turtle",
        "type": "Monster",
        "strength": "+2",
        "level": 1,
        "portrait": "Attack Turtle.png",
        "output": "Attack Turtle Card.png",
        "description": "Slow, steady, vicious.",
        "trait": {
            "name": "Hard Shell",
            "text": "You have +2 Str.",
        },
        "curse": {
            "name": "Yer a Hare, Wizard",
            "text": (
                "Pathetic. You lost\u2026 to a turtle. Slowpoke. "
                'Treat all "6" movement cards as a "1".'
            ),
        },
    },

    "rake": {
        "name": "Rake",
        "type": "Monster",
        "strength": "+2",
        "level": 1,
        "portrait": "Rake.png",
        "output": "Rake Card.png",
        "description": "Watch your step!",
        "trait": {
            "name": "Rake It In!",
            "text": (
                "When drawing an Equip card, you may discard one of "
                "your Equip cards to draw a second from the same "
                "level as the first."
            ),
        },
        "curse": {
            "name": "Eughghghghgh",
            "text": (
                "Snap! If you have more Curses than Traits, treat "
                "all 1 movement cards as a 0. If you play a 0, "
                "reactivate the current tile."
            ),
        },
    },

    "cursed_teddy_bear": {
        "name": "Cursed Teddy Bear",
        "type": "Monster",
        "strength": "+2",
        "level": 1,
        "portrait": "Cursed Teddy Bear.png",
        "output": "Cursed Teddy Bear Card.png",
        "description": "So\u2026 darn\u2026 cute\u2026",
        "trait": {
            "name": "I'm a Grown-up Now!",
            "text": "Add a +3 Str. Ted Bearson Minion Card to your Player Board.",
        },
        "curse": {
            "name": "Together Forever",
            "text": (
                "He won\u2019t let go! Add a \u22122 Str Lonely Teddy Item "
                "Card to your pack. It takes up one slot."
            ),
        },
    },

    "trouser_snake": {
        "name": "Trouser Snake",
        "type": "Monster",
        "strength": "+3",
        "level": 1,
        "portrait": "Trouser Snake.png",
        "output": "Trouser Snake Card.png",
        "description": "Surprise!",
        "trait": {
            "name": "BDE",
            "text": "You have +5 Str. when wearing no Footgear.",
        },
        "curse": {
            "name": "It Got In!",
            "text": "Discard any equipped Footgear, and any Footgear in your pack.",
        },
    },

    "big_rat": {
        "name": "Big Rat",
        "type": "Monster",
        "strength": "+3",
        "level": 1,
        "portrait": "Big Rat.png",
        "output": "Big Rat Card.png",
        "description": "Unusually large.",
        "trait": {
            "name": "No More Charlie Work!",
            "text": (
                "When fighting a monster, you may choose to fight one "
                "1 tier higher than your current tier location."
            ),
        },
        "curse": {
            "name": "Bit o' the Plague",
            "text": "You have -2 Str.",
        },
    },

    "slightly_bigger_rat": {
        "name": "Slightly Bigger Rat",
        "type": "Monster",
        "strength": "+4",
        "level": 1,
        "portrait": "Slightly Bigger Rat.png",
        "output": "Slightly Bigger Rat Card.png",
        "description": "Even less usually sized.",
        "trait": {
            "name": "Rat Smasher",
            "text": "You automatically win any battles against rats or cats.",
        },
        "curse": {
            "name": "Bit More Plague",
            "text": "You have -3 Str.",
        },
    },

    "diseased_gnome": {
        "name": "Diseased Gnome",
        "type": "Monster",
        "strength": "+5",
        "level": 1,
        "portrait": "Diseased Gnome.png",
        "output": "Diseased Gnome Card.png",
        "description": "They're mostly STI's.",
        "trait": {
            "name": "Immunized",
            "text": "Negate the next curse you would receive.",
        },
        "curse": {
            "name": "It's Taking Over!",
            "text": (
                "Something itches - Discard any items "
                "equipped to your legs or chest."
            ),
        },
    },

    "rusty_golem": {
        "name": "Rusty Golem",
        "type": "Monster",
        "strength": "+6",
        "level": 1,
        "portrait": "Rusty Golem.png",
        "output": "Rusty Golem Card.png",
        "description": "It has seen better days.",
        "trait": {
            "name": "Rust Immunity",
            "text": "You are immune to any cards that cause you to discard weapons.",
        },
        "curse": {
            "name": "The Rust is Spreading!",
            "text": "Discard all equipped Weapons.",
        },
    },

    "penis_fly_trap": {
        "name": "Penis Fly Trap",
        "type": "Monster",
        "strength": "+6",
        "level": 1,
        "portrait": "Penis Fly Trap.png",
        "output": "Penis Fly Trap Card.png",
        "description": "Bonus: +3 Attack vs. Men",
        "trait": {
            "name": "Phallic Dexterity",
            "text": (
                "Your junk is able to protect itself! "
                "You are immune to curses that affect footgear."
            ),
        },
        "curse": {
            "name": "Botched Circumcision",
            "text": (
                "Your movement cards have a value of 1 less, "
                "with a minimum value of 1."
            ),
        },
    },

    "wrecking_ball": {
        "name": "Wrecking Ball",
        "type": "Monster",
        "strength": "+8",
        "level": 1,
        "portrait": "Wrecking Ball.png",
        "output": "Wrecking Ball Card.png",
        "description": "Please come in!",
        "trait": {
            "name": "Ball and Chain",
            "text": 'Take the "Ball and Chain" Item card (+7 Str. 1 handed).',
        },
        "curse": {
            "name": "Get Rekt",
            "text": (
                "Discard your highest-Str equipped item."
            ),
        },
    },

    "cat_with_a_grudge": {
        "name": "Cat with a Grudge",
        "type": "Monster",
        "strength": "+9",
        "level": 1,
        "portrait": "Cat with a Grudge.png",
        "output": "Cat with a Grudge Card.png",
        "description": "He thinks you killed his father.",
        "trait": {
            "name": "8 Lives to Go!",
            "text": "You may discard this card to remove one Tier 1 or 2 curse.",
        },
        "curse": {
            "name": "That'll Leave a Mark!",
            "text": "You have -3 Str.",
        },
    },

    "stoned_golem": {
        "name": "Stoned Golem",
        "type": "Monster",
        "strength": "+11",
        "level": 2,
        "portrait": "Stoned Golem.png",
        "output": "Stoned Golem Card.png",
        "description": "It keeps giggling\u2026",
        "trait": {
            "name": "My Hands are Awesome\u2026",
            "text": (
                "Increase your movement card hand size by 1."
            ),
        },
        "curse": {
            "name": "Dude, Where's My Card?",
            "text": (
                "You may only hold a maximum of 3 movement cards. "
                "Discard if you currently have more than 3."
            ),
        },
    },

    "acid_dragon": {
        "name": "Acid Dragon",
        "type": "Monster",
        "strength": "+13",
        "level": 2,
        "portrait": "Acid Dragon.png",
        "output": "Acid Dragon Card.png",
        "description": "Spittin' acid and trippin' balls.",
        "trait": {
            "name": "I See Everything!",
            "text": (
                "When you draw a Monster card, you may put it at the bottom "
                "of the deck and draw another."
            ),
        },
        "curse": {
            "name": "Bad Trip",
            "text": (
                "You cannot look at your movement cards. "
                "They must be kept facedown and played randomly."
            ),
        },
    },

    "demonic_analrapist": {
        "name": "Demonic Analrapist",
        "type": "Monster",
        "strength": "+14",
        "level": 2,
        "portrait": "Demonic Analrapist.png",
        "output": "Demonic Analrapist Card.png",
        "description": "He's an analyst AND a therapist!",
        "trait": {
            "name": "Leather Daddy",
            "text": "Add a +1 Str. Token to this card every time you lose a battle.",
        },
        "curse": {
            "name": "Nevernude",
            "text": "You have -5 Str. for every empty Equip slot.",
        },
    },

    "smelly_cat": {
        "name": "Smelly Cat",
        "type": "Monster",
        "strength": "+16",
        "level": 2,
        "portrait": "Smelly Cat.png",
        "output": "Smelly Cat Card.png",
        "description": "What are they feeding it?",
        "trait": {
            "name": "It's Not Your Fault!",
            "text": (
                "If you lose a battle, you may discard this card to take that "
                "Monster's Trait instead of its Curse."
            ),
        },
        "curse": {
            "name": "The Smell Won't Come Out!",
            "text": (
                "Discard 2 Equip cards of your choice from your Player Board."
            ),
        },
    },

    "wood_golem": {
        "name": "Wood Golem",
        "type": "Monster",
        "strength": "+18",
        "level": 2,
        "portrait": "Wood Golem.png",
        "output": "Wood Golem Card.png",
        "description": "Stronger in the morning.",
        "trait": {
            "name": "Bark Worse Than its Bite",
            "text": "For every empty Equip slot, you have +3 Str.",
        },
        "curse": {
            "name": "Termites!",
            "text": "You have -5 Str.",
        },
    },

    "bad_mexican_food": {
        "name": "Bad Mexican Food",
        "type": "Monster",
        "strength": "+19",
        "level": 2,
        "portrait": "Bad Mexican Food.png",
        "output": "Bad Mexican Food Card.png",
        "description": "Even spicier on its way out.",
        "trait": {
            "name": "Stomach of Steel",
            "text": "You have +3 Str.",
        },
        "curse": {
            "name": "I Need a Place to Go!",
            "text": "If you're wearing boots, discard them.",
        },
    },

    "fat_troll": {
        "name": "Fat Troll",
        "type": "Monster",
        "strength": "+20",
        "level": 2,
        "portrait": "Fat Troll.png",
        "output": "Fat Troll Card.png",
        "description": 'Or was it "fat roll"?',
        "trait": {
            "name": "Big Boned!",
            "text": (
                "You are so large, you can have 2 Chest armours equipped at once."
            ),
        },
        "curse": {
            "name": "So\u2026 Lethargic\u2026",
            "text": (
                "Whenever you use a 3 or a 4, add a -1 Str. token to this card."
            ),
        },
    },

    "one_of_those_fish": {
        "name": "One of Those Fish That Swim Up Your Urethra",
        "type": "Monster",
        "strength": "+21",
        "level": 3,
        "portrait": "One of those fish that swim up your urethra.png",
        "output": "One of those fish that swim up your urethra Card.png",
        "description": "Ew.",
        "trait": {
            "name": "Strong Schlong",
            "text": (
                "Add five +1 Str. tokens to this card. When your opponent enters "
                "battle, you may discard one or more to give them -3 Str."
            ),
        },
        "curse": {
            "name": "It's Wriggling!",
            "text": (
                "Whenever you take on a new curse, discard a trait of your choice."
            ),
        },
    },

    "spooky_ghost": {
        "name": "Spooky Ghost",
        "type": "Monster",
        "strength": "+23",
        "level": 3,
        "portrait": "Spooky Ghost.png",
        "output": "Spooky Ghost Card.png",
        "description": "It's 3 spooky 5 me.",
        "trait": {
            "name": "Phase Shift",
            "text": (
                "Before you move, you may discard 1 Equip card to change "
                "time of day."
            ),
        },
        "curse": {
            "name": "Out of Phase",
            "text": "Your pack can only carry 1 item instead of 3.",
        },
    },

    "wicked_witch": {
        "name": "Wicked Witch",
        "type": "Monster",
        "strength": "+23",
        "level": 3,
        "portrait": "Wicked Witch.png",
        "output": "Wicked Witch Card.png",
        "description": "Hotter than they used to be.",
        "trait": {
            "name": "She's Melting!",
            "text": (
                'Take a "Vial of Liquid Witch" card. You may discard it to '
                "give a monster or player -10 Str. for one battle."
            ),
        },
        "curse": {
            "name": "Cursed!",
            "text": (
                "The next time you face a monster (other than the Werbler) "
                "discard this card. You lose that battle."
            ),
        },
    },

    "spanish_inquisition": {
        "name": "Spanish Inquisition",
        "type": "Monster",
        "strength": "+25",
        "level": 3,
        "portrait": "Spanish Inquisition.png",
        "output": "Spanish Inquisition Card.png",
        "description": "Didn't expect that!",
        "trait": {
            "name": "I'll Come In Again",
            "text": (
                "When drawing a Monster card, you may shuffle it into the deck "
                "and draw another."
            ),
        },
        "curse": {
            "name": "Now, Cardinal, the Rack!",
            "text": (
                "Discard 1 Trait or Equip card for every curse afflicting you."
            ),
        },
    },

    "creepy_hollywood_exec": {
        "name": "Creepy Hollywood Exec",
        "type": "Monster",
        "strength": "+25",
        "level": 3,
        "portrait": "Creepy Hollywood Exec.png",
        "output": "Creepy Hollywood Exec Card.png",
        "description": "Bonus: If Roofie Demon has been defeated, you win this battle.",
        "trait": {
            "name": "Me Too!",
            "text": (
                "Whenever an opponent discards a curse, you may discard one "
                "of your own."
            ),
        },
        "curse": {
            "name": "Blacklisted",
            "text": 'Go back to "Start".',
        },
    },

    "necrodancer": {
        "name": "Necrodancer",
        "type": "Monster",
        "strength": "+25",
        "level": 3,
        "portrait": "Necrodancer.png",
        "output": "Necrodancer Card.png",
        "description": "Busting moves and raising dudes.",
        "trait": {
            "name": "Fancy Footwork",
            "text": (
                "When playing a movement card, you may give it -1 or -2 "
                "if you wish."
            ),
        },
        "curse": {
            "name": "Can't Stop the Music!",
            "text": (
                'Replace your Footgear with -5 Str. "Dancing Shoes" '
                "and discard any card it replaces."
            ),
        },
    },

    "guy_with_a_gun": {
        "name": "Guy With a Gun",
        "type": "Monster",
        "strength": "+26",
        "level": 3,
        "portrait": "Guy with a gun.png",
        "output": "Guy with a gun Card.png",
        "description": "Unoriginal, but still dangerous.",
        "trait": {
            "name": "Kapwing!",
            "text": 'Take a +8 Str. "Bulletproof Vest" card.',
        },
        "curse": {
            "name": "Shot Through the Heart",
            "text": (
                "If you have Chest armour, discard it. "
                "If you don't, you have a permanent -5 Str."
            ),
        },
    },

    "velociraptor": {
        "name": "Velociraptor",
        "type": "Monster",
        "strength": "+28",
        "level": 3,
        "portrait": "Velociraptor.png",
        "output": "Velociraptor Card.png",
        "description": "Where's Chris Pratt when you need him?",
        "trait": {
            "name": "You're the Alpha!",
            "text": "Gain a +7 Str. Pet Velociraptor Minion card.",
        },
        "curse": {
            "name": "Clever Girl",
            "text": "Discard all items in your pack.",
        },
    },

    "roofie_demon": {
        "name": "Roofie Demon",
        "type": "Monster",
        "strength": "+29",
        "level": 3,
        "portrait": "Roofie Demon.png",
        "output": "Roofie Demon Card.png",
        "portrait_brightness": 1.35,
        "description": "Bonus: If Creepy Hollywood Exec has been defeated, you win this battle.",
        "trait": {
            "name": "Residuals",
            "text": "Every turn, add a +1 Str. token to this card.",
        },
        "curse": {
            "name": "My Drink Tastes Funny\u2026",
            "text": "Discard 2 currently equipped cards.",
        },
    },

    "jeffrey_dahmer_as_a_vampire": {
        "name": "Jeffrey Dahmer as a Vampire",
        "type": "Monster",
        "strength": "+30",
        "level": 3,
        "portrait": "Jeffrey Dahmer as a Vampire.png",
        "output": "Jeffrey Dahmer as a Vampire Card.png",
        "description": "Kinda overkill, right?",
        "trait": {
            "name": "Strengthened by Taint",
            "text": "You have +2 Str. for every curse afflicting you.",
        },
        "curse": {
            "name": "He Drank Your Blood. Then Ate Your Arm.",
            "text": (
                "You have -5 Str. Replace your right arm Equip slot with this card, "
                "discarding anything it replaces."
            ),
        },
    },

    # ── New monsters added to card generator ─────────────────────────────

    "coronavirus": {
        "name": "Coronavirus",
        "type": "Monster",
        "strength": "+19",
        "level": 2,
        "portrait": "Coronavirus.png",
        "output": "Coronavirus Card.png",
        "description": "Guess when I started working on this game!",
        "trait": {
            "name": "Vaxxed!",
            "text": "You cannot take on any new Tier 2 curses.",
        },
        "curse": {
            "name": "Facial Coverings Required",
            "text": "If you have no Helm equipped, you have -10 Str.",
        },
    },

    "twisted_treant": {
        "name": "Twisted Treant",
        "type": "Monster",
        "strength": "+17",
        "level": 2,
        "portrait": "Twisted Treant.png",
        "output": "Twisted Treant Card.png",
        "description": "He needs a hug.",
        "trait": {
            "name": "Tough Skin",
            "text": "If you are wearing no Chest Armour, you have +10 Str.",
        },
        "curse": {
            "name": "Flooded Base!",
            "text": "Discard all cards currently in your pack.",
        },
    },

    "zombie_linebacker": {
        "name": "Zombie Linebacker",
        "type": "Monster",
        "strength": "+22",
        "level": 3,
        "portrait": "Zombie Linebacker.png",
        "output": "Zombie Linebacker Card.png",
        "description": "TBD",
        "trait": {
            "name": "Touchdown!",
            "text": (
                "You have +3 Str. You may also move directly to "
                "The Werbler\u2019s tile at any time."
            ),
        },
        "curse": {
            "name": "Roughing the Kicker!",
            "text": "Move back 15 spaces.",
        },
    },

    "goblin_warrior": {
        "name": "Goblin Warrior",
        "type": "Monster",
        "strength": "+26",
        "level": 3,
        "portrait": "Goblin Warrior.png",
        "output": "Goblin Warrior Card.png",
        "description": "He's got a mean streak.",
        "trait": {
            "name": "Scavenger",
            "text": "When opening a Chest, draw 2 items and choose 1.",
        },
        "curse": {
            "name": "Stabbed",
            "text": "You have -1 Str. for every curse afflicting you.",
        },
    },

    "large_orc": {
        "name": "Large Orc",
        "type": "Monster",
        "strength": "+23",
        "level": 3,
        "portrait": "Large Orc.png",
        "output": "Large Orc Card.png",
        "description": "Bigger than the others.",
        "trait": {
            "name": "Meat's Back On the Menu!",
            "text": "When you defeat a monster, gain a random item from its level.",
        },
        "curse": {
            "name": "You're On the Menu\u2026",
            "text": (
                'Replace one Weapon slot with a \u22122 Str. "Bloody Stump" card. '
                "Discard anything it replaces."
            ),
        },
    },

    "swamp_monster": {
        "name": "Swamp Monster",
        "type": "Monster",
        "strength": "+24",
        "level": 3,
        "portrait": "Swamp Monster.png",
        "output": "Swamp Monster Card.png",
        "description": "It smells awful.",
        "trait": {
            "name": "He's Just Misunderstood!",
            "text": 'Gain a +6 Str. "Swamp Friend" Minion card.',
        },
        "curse": {
            "name": "Laundry Day!",
            "text": "Discard all equipped armour (Helmet, Chest, and Leg).",
        },
    },

    "skeletal_overlord": {
        "name": "Skeletal Overlord",
        "type": "Monster",
        "strength": "+27",
        "level": 3,
        "portrait": "Skeletal Overlord.png",
        "output": "Skeletal Overlord Card.png",
        "description": "King of the bone zone.",
        "trait": {
            "name": "I'm De Overlord Now.",
            "text": (
                "Gain a +5 Str. Skeletal Minion card. "
                "Each Skeletal Minion gives +1 Str. to all your other minions."
            ),
        },
        "curse": {
            "name": "Enslaved!",
            "text": "Give one of your equipped items to an opponent.",
        },
    },

    "demon_lord": {
        "name": "Demon Lord",
        "type": "Monster",
        "strength": "+27",
        "level": 3,
        "portrait": "Demon Lord.png",
        "output": "Demon Lord Card.png",
        "description": "He means business.",
        "trait": {
            "name": "New Lord in Town.",
            "text": 'Gain a +7 Str. "Demon Spawn" Minion card.',
        },
        "curse": {
            "name": "KNEEL!",
            "text": "Add +10 Str. to the Werbler\u2019s Strength.",
        },
    },

    "sinkhole": {
        "name": "Sinkhole",
        "type": "Monster",
        "strength": "+14",
        "level": 2,
        "portrait": "Sinkhole.png",
        "output": "Sinkhole Card.png",
        "description": "Watch your step!",
        "trait": {
            "name": "Swiftness",
            "text": "When playing a movement card, you may add +1 to its value.",
        },
        "curse": {
            "name": "Quite the Setback!",
            "text": (
                "Move back 10 spaces and discard all 3 and 4 movement "
                "cards currently in your hand."
            ),
        },
    },

    "blood_golem": {
        "name": "Blood Golem",
        "type": "Monster",
        "strength": "+15",
        "level": 2,
        "portrait": "Blood Golem.png",
        "output": "Blood Golem Card.png",
        "description": "It's oozing everywhere.",
        "trait": {
            "name": "Blood Pact",
            "text": "You have +3 Str.",
        },
        "curse": {
            "name": "Blood Drain",
            "text": "You have -4 Str.",
        },
    },

    "gremlin_warrior": {
        "name": "Gremlin Warrior",
        "type": "Monster",
        "strength": "+7",
        "level": 1,
        "portrait": "Gremlin Warrior.png",
        "output": "Gremlin Warrior Card.png",
        "description": "Don't feed it after midnight!",
        "trait": {
            "name": "Gremlin's Cunning",
            "text": "You have +2 Str.",
        },
        "curse": {
            "name": "Don't Get It Wet!",
            "text": "You have -2 Str.",
        },
    },

    "bogeyman": {
        "name": "Bogeyman",
        "type": "Monster",
        "strength": "+18",
        "level": 2,
        "portrait": "Spooky Ghost.png",
        "output": "Bogeyman Card.png",
        "description": "Time to boogie.",
        "trait": {
            "name": "You Got a Birdie!",
            "text": "Take a Power Driver Equip Card (2h, +10 Str).",
        },
        "curse": {
            "name": "Scared of the Dark",
            "text": "-5 Str during Night.",
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
MONSTERS_DIR = Path("Images/Monsters")
PORTRAITS_DIR = MONSTERS_DIR / "Portraits"
FINISHED_DIR = MONSTERS_DIR / "Finished Cards"
TEMPLATE_PATH = MONSTERS_DIR / "Monster Card Template.png"

CARD_W, CARD_H = 1024, 1536

# Portrait window (transparent region in template)
PORTRAIT_WINDOW_TOP = 220
PORTRAIT_WINDOW_BOTTOM = 1030
PORTRAIT_WINDOW_LEFT = 48
PORTRAIT_WINDOW_RIGHT = 1008

# Top frame labels
TYPE_LABEL_POS = (160, 55)       # "Monster" in the frame band
STRENGTH_POS = (910, 62)         # strength in the gold flap

# Name banner (parchment, y ≈ 115–230)
NAME_BANNER_TOP = 115
NAME_BANNER_BOTTOM = 230

# Bottom text area (parchment)
TEXT_AREA_TOP = 1060
TEXT_AREA_LEFT = 100
TEXT_AREA_RIGHT = 924
TEXT_AREA_BOTTOM = 1480
TEXT_LINE_HEIGHT_FACTOR = 1.30

# Two-column layout
COLUMN_GAP = 30          # horizontal gap around the divider line
DIVIDER_X = CARD_W // 2  # vertical divider at centre

LEFT_COL_LEFT = TEXT_AREA_LEFT
LEFT_COL_RIGHT = DIVIDER_X - COLUMN_GAP // 2
RIGHT_COL_LEFT = DIVIDER_X + COLUMN_GAP // 2
RIGHT_COL_RIGHT = TEXT_AREA_RIGHT


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


font_type_label = _load_font("Cinzel-Black.ttf", 38)
font_strength = _load_font("Cinzel-Black.ttf", 56)
font_name = _load_font("Almendra-Bold.ttf", 64)
font_description = _load_font("MedievalSharp-Oblique.ttf", 30)  # italic blurb
font_section_title = _load_font("Cinzel-Black.ttf", 30)
font_ability_name = _load_font("MedievalSharp-Bold.ttf", 32)
font_ability_text = _load_font("MedievalSharp.ttf", 30)


# ═══════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════
COLOR_CREAM = (255, 240, 200)
COLOR_DARK = (30, 15, 5)
COLOR_DARK_BROWN = (60, 35, 10)
COLOR_TRAIT_HEADER = (30, 85, 25)       # dark green — section header
COLOR_TRAIT_NAME = (75, 115, 70)        # muted sage green — ability name
COLOR_CURSE_HEADER = (130, 25, 15)      # dark red — section header
COLOR_CURSE_NAME = (155, 65, 55)        # muted dusty red — ability name
COLOR_DIVIDER = (80, 45, 15, 255)       # brown divider line


# ═══════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    x_center: int = CARD_W // 2,
) -> int:
    """Draw text horizontally centred. Returns the bottom y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x_center - tw // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + th


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


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_width: int,
    line_height_factor: float = TEXT_LINE_HEIGHT_FACTOR,
    center: bool = False,
    x_left: int = TEXT_AREA_LEFT,
    dry_run: bool = False,
) -> int:
    """Pixel-accurate word-wrap. Returns final y after the last line."""
    lines = _pixel_wrap(draw, text, font, max_width)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lh = int((bbox[3] - bbox[1]) * line_height_factor)
        if not dry_run:
            if center:
                lw = bbox[2] - bbox[0]
                x = x_left + (max_width - lw) // 2
            else:
                x = x_left
            draw.text((x, y), line, font=font, fill=fill)
        y += lh
    return y


def measure_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    line_height_factor: float = TEXT_LINE_HEIGHT_FACTOR,
) -> int:
    """Measure the pixel height of wrapped text without drawing."""
    return draw_wrapped_text(
        draw, text, 0, font, (0, 0, 0), max_width,
        line_height_factor=line_height_factor,
        dry_run=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CARD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_card(monster: dict) -> Path:
    """Generate a single monster card and return the output path."""
    portrait_path = PORTRAITS_DIR / monster["portrait"]
    output_path = FINISHED_DIR / monster["output"]

    if not portrait_path.exists():
        print(f"  SKIP — portrait not found: {portrait_path}")
        return output_path

    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    # Per-monster portrait brightness adjustment
    if "portrait_brightness" in monster:
        p_rgb = portrait.convert("RGB")
        p_bright = ImageEnhance.Brightness(p_rgb).enhance(monster["portrait_brightness"])
        p_bright_rgba = p_bright.convert("RGBA")
        p_bright_rgba.putalpha(portrait.getchannel("A"))
        portrait = p_bright_rgba

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

    # ------------------------------------------------------------------
    # TOP FRAME — type label and strength
    # ------------------------------------------------------------------
    draw.text(TYPE_LABEL_POS, monster["type"].upper(),
              font=font_type_label, fill=COLOR_CREAM)

    str_text = monster["strength"]
    s_bbox = draw.textbbox((0, 0), str_text, font=font_strength)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text((STRENGTH_POS[0] - s_w // 2, STRENGTH_POS[1]),
              str_text, font=font_strength, fill=COLOR_DARK)

    # ------------------------------------------------------------------
    # NAME BANNER — centred with gentle arc
    # ------------------------------------------------------------------
    hero_name_font = font_name
    NAME_BANNER_HPAD = 60
    max_name_w = CARD_W - NAME_BANNER_HPAD * 2
    banner_h = NAME_BANNER_BOTTOM - NAME_BANNER_TOP

    name_bbox = draw.textbbox((0, 0), monster["name"], font=hero_name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]
    cur_name_size = hero_name_font.size

    while (name_w > max_name_w or name_h > banner_h) and cur_name_size > 20:
        cur_name_size -= 1
        hero_name_font = _load_font("Almendra-Bold.ttf", cur_name_size)
        name_bbox = draw.textbbox((0, 0), monster["name"], font=hero_name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]

    long_offset = int(round(0.012 * max(0, name_w - 500)))  # longer → lower
    name_y = NAME_BANNER_TOP + (banner_h - name_h) // 2 + 3 + long_offset
    name_y = max(NAME_BANNER_TOP, name_y)
    arc = int(round(-5 - 0.018 * max(0, name_w - 500)))

    name_y_center = name_y + name_h // 2
    draw_curved_text(canvas, monster["name"], name_y_center, hero_name_font,
                     COLOR_DARK, arc_depth=arc)
    draw = ImageDraw.Draw(canvas)  # refresh after alpha_composite

    # ------------------------------------------------------------------
    # BOTTOM TEXT AREA
    # ------------------------------------------------------------------
    text_width = TEXT_AREA_RIGHT - TEXT_AREA_LEFT
    left_col_w = LEFT_COL_RIGHT - LEFT_COL_LEFT
    right_col_w = RIGHT_COL_RIGHT - RIGHT_COL_LEFT

    # --- Fixed horizontal rule position (consistent across all cards) ---
    BLURB_PAD = 20  # equal gap above and below the blurb text
    # Use a reference line height so HRULE_Y is identical for every card
    _ref_bbox = draw.textbbox((0, 0), "Xg", font=font_description)
    _ref_h = int((_ref_bbox[3] - _ref_bbox[1]) * TEXT_LINE_HEIGHT_FACTOR)
    HRULE_Y = TEXT_AREA_TOP + BLURB_PAD + _ref_h + BLURB_PAD

    # --- Description (italic, centred horizontally, fixed y) ---
    desc_text = monster["description"]
    desc_y = TEXT_AREA_TOP + BLURB_PAD - 3

    # Auto-scale the blurb font down if it doesn't fit on one line
    desc_font = font_description
    if draw.textlength(desc_text, font=desc_font) > text_width:
        desc_size = desc_font.size
        while draw.textlength(desc_text, font=desc_font) > text_width and desc_size > 16:
            desc_size -= 1
            desc_font = _load_font("MedievalSharp-Oblique.ttf", desc_size)

    draw_wrapped_text(
        draw, desc_text, desc_y,
        desc_font, COLOR_DARK_BROWN, text_width,
        center=True,
        x_left=TEXT_AREA_LEFT,
    )

    # --- Horizontal rule under description ---
    hrule_y = HRULE_Y
    draw.line(
        [(TEXT_AREA_LEFT, hrule_y), (TEXT_AREA_RIGHT, hrule_y)],
        fill=COLOR_DIVIDER, width=2,
    )
    y = hrule_y + 14  # gap below horizontal rule

    columns_zone_top = y   # top of the available column zone
    NAME_TO_TEXT_GAP = 12  # gap between trait/curse name and body text
    HEADER_TO_NAME_GAP = 28

    trait = monster["trait"]
    curse = monster["curse"]

    # --- Measure both columns (dry run) to find total height ---
    # Header height (same for both)
    th_bbox = draw.textbbox((0, 0), "TRAIT", font=font_section_title)
    th_h = th_bbox[3] - th_bbox[1]

    def _measure_column(name_text: str, body_text: str, col_w: int) -> int:
        """Return total pixel height for: header + gap + name + gap + body."""
        h = th_h + HEADER_TO_NAME_GAP
        h = measure_wrapped(draw, name_text, font_ability_name, col_w) + h
        h += NAME_TO_TEXT_GAP
        h = measure_wrapped(draw, body_text, font_ability_text, col_w) + h
        return h

    trait_h = _measure_column(trait["name"], trait["text"], left_col_w)
    curse_h = _measure_column(curse["name"], curse["text"], right_col_w)
    tallest = max(trait_h, curse_h)

    # Vertically centre the block (biased upward) between the rule and bottom
    available = TEXT_AREA_BOTTOM - columns_zone_top
    top_pad = max(0, (available - tallest) // 5)  # 1/5 above, 4/5 below
    y = columns_zone_top + top_pad

    columns_top = columns_zone_top  # vertical divider starts at the horiz rule

    # --- Section headers (TRAIT / CURSE) ---
    th_w = th_bbox[2] - th_bbox[0]
    th_x = LEFT_COL_LEFT + (left_col_w - th_w) // 2
    draw.text((th_x, y), "TRAIT", font=font_section_title,
              fill=COLOR_TRAIT_HEADER)

    ch_bbox = draw.textbbox((0, 0), "CURSE", font=font_section_title)
    ch_w = ch_bbox[2] - ch_bbox[0]
    ch_x = RIGHT_COL_LEFT + (right_col_w - ch_w) // 2
    draw.text((ch_x, y), "CURSE", font=font_section_title,
              fill=COLOR_CURSE_HEADER)

    y += th_h + HEADER_TO_NAME_GAP

    # --- Trait column (left) ---
    trait_y = y
    trait_y = draw_wrapped_text(
        draw, trait["name"], trait_y,
        font_ability_name, COLOR_TRAIT_NAME, left_col_w,
        center=True, x_left=LEFT_COL_LEFT,
    )
    trait_y += NAME_TO_TEXT_GAP
    trait_y = draw_wrapped_text(
        draw, trait["text"], trait_y,
        font_ability_text, COLOR_DARK, left_col_w,
        center=True, x_left=LEFT_COL_LEFT,
    )

    # --- Curse column (right) ---
    curse_y = y
    curse_y = draw_wrapped_text(
        draw, curse["name"], curse_y,
        font_ability_name, COLOR_CURSE_NAME, right_col_w,
        center=True, x_left=RIGHT_COL_LEFT,
    )
    curse_y += NAME_TO_TEXT_GAP
    curse_y = draw_wrapped_text(
        draw, curse["text"], curse_y,
        font_ability_text, COLOR_DARK, right_col_w,
        center=True, x_left=RIGHT_COL_LEFT,
    )

    # --- Vertical divider (drawn as rect for consistent rendering) ---
    col_bottom = TEXT_AREA_BOTTOM - 6  # just above the bottom card line
    divider_color_light = (COLOR_DIVIDER[0], COLOR_DIVIDER[1], COLOR_DIVIDER[2], 160)
    draw.rectangle(
        [(DIVIDER_X, hrule_y), (DIVIDER_X + 1, col_bottom)],
        fill=divider_color_light,
    )

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
    args = [a.lower() for a in sys.argv[1:]]

    if not args:
        keys = list(MONSTERS.keys())
    else:
        keys = args

    for key in keys:
        if key not in MONSTERS:
            print(f"  Unknown monster key: '{key}'")
            print(f"  Available: {', '.join(MONSTERS.keys())}")
            continue
        m = MONSTERS[key]
        print(f"Generating {m['name']}...")
        generate_card(m)

    print("Done.")


if __name__ == "__main__":
    main()
