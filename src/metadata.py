"""Small, topic-matched hashtag sets for bank and generated Shorts."""
import re

TOPICS = (
    (r"\b(chatgpt|openai)\b", "#ChatGPT"),
    (r"\b(large language model|llm|llms)\b", "#LargeLanguageModels"),
    (r"\b(machine learning)\b", "#MachineLearning"),
    (r"\b(ai|artificial intelligence)\b", "#ArtificialIntelligence"),
    (r"\b(robot|robots|robotics)\b", "#Robotics"),
    (r"\b(rocket|rockets|spacecraft)\b", "#RocketScience"),
    (r"\b(mars)\b", "#Mars"),
    (r"\b(earth|planet|planets)\b", "#PlanetEarth"),
    (r"\b(black hole|black holes)\b", "#BlackHoles"),
    (r"\b(ocean|oceans)\b", "#OceanScience"),
    (r"\b(climate)\b", "#ClimateScience"),
    (r"\b(dna|gene|genes|genetics)\b", "#Genetics"),
    (r"\b(protein|proteins|alphafold)\b", "#ProteinScience"),
    (r"\b(brain|neuron|neurons)\b", "#Neuroscience"),
    (r"\b(battery|batteries)\b", "#BatteryTechnology"),
    (r"\b(solar)\b", "#SolarEnergy"),
    (r"\b(fusion)\b", "#FusionEnergy"),
    (r"\b(quantum)\b", "#QuantumScience"),
    (r"\b(gta|grand theft auto)\b", "#GTA6"),
    (r"\b(rockstar)\b", "#RockstarGames"),
    (r"\b(mod|mods|modders)\b", "#GameMods"),
)
THEMES = {"ai": "#ArtificialIntelligence", "planet": "#EarthScience",
          "biology": "#Biology", "future-tech": "#FutureTechnology", "gaming": "#Gaming"}


def hashtags(script: dict) -> list[str]:
    """Prioritize the title, then narration; never carry stale creator/trend tags."""
    selected = []
    for text in (script.get("title", ""), " ".join(script.get("sentences", []))):
        for pattern, tag in TOPICS:
            if re.search(pattern, text, re.IGNORECASE) and tag not in selected:
                selected.append(tag)
    theme = THEMES.get(script.get("theme"), "#Science")
    if theme not in selected:
        selected.append(theme)
    return [*selected[:3], "#Shorts", "#MAKOKOGW"]