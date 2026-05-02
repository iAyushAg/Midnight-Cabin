import json
import random
from datetime import datetime

ideas = [
    {
        "theme": "Midnight cabin rain with brown noise",
        "title": "Deep Cabin Rain & Brown Noise for Sleep and Focus",
        "sound_layers": ["brown_noise", "rain", "soft_thunder"],
        "visual": "dark cozy cabin window with rain at midnight"
    },
    {
        "theme": "Ocean waves with deep focus noise",
        "title": "Dark Ocean Waves with Deep Brown Noise for Focus",
        "sound_layers": ["brown_noise", "ocean_waves"],
        "visual": "moonlit ocean waves at night"
    },
    {
        "theme": "Forest night ambience",
        "title": "Peaceful Forest Night Ambience for Deep Sleep",
        "sound_layers": ["pink_noise", "night_forest", "soft_wind"],
        "visual": "quiet forest under moonlight"
    },
    {
        "theme": "Fireplace and winter wind",
        "title": "Cozy Fireplace and Winter Wind for Sleep",
        "sound_layers": ["fireplace", "wind", "brown_noise"],
        "visual": "warm fireplace inside snowy cabin"
    }
]

idea = random.choice(ideas)
idea["created_at"] = datetime.now().isoformat()

with open("current_idea.json", "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))