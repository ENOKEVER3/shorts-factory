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
    (r"\b(earth)\b", "#PlanetEarth"),
    (r"\b(moon|lunar)\b", "#Moon"),
    (r"\b(black hole|black holes)\b", "#BlackHoles"),
    (r"\b(ocean|oceans)\b", "#OceanScience"),
    (r"\b(climate)\b", "#ClimateScience"),
    (r"\b(dna|gene|genes|genetics)\b", "#Genetics"),
    (r"\b(protein|proteins|alphafold)\b", "#ProteinScience"),
    (r"\b(brain|neuron|neurons)\b", "#Neuroscience"),
    (r"\b(battery|batteries)\b", "#BatteryTechnology"),
    (r"\b(solar panel|solar panels|solar power|solar energy)\b", "#SolarEnergy"),
    (r"\b(fusion)\b", "#FusionEnergy"),
    (r"\b(quantum)\b", "#QuantumScience"),
    (r"\b(nasa|apollo|voyager|webb)\b", "#NASA"),
    (r"\b(the sun|solar flare|solar storm)\b", "#TheSun"),
    (r"\b(solar eclipse)\b", "#SolarEclipse"),
    (r"\b(lunar eclipse)\b", "#LunarEclipse"),
    (r"\b(saturn|jupiter|venus)\b", "#SolarSystem"),
    (r"\b(antarctica|antarctic)\b", "#Antarctica"),
    (r"\b(einstein|time dilation)\b", "#Physics"),
    (r"\b(internet|cable|cables)\b", "#HowTheInternetWorks"),
    (r"\b(airplane|airplanes|aircraft|jets)\b", "#Aviation"),
    (r"\b(sleep|asleep)\b", "#SleepScience"),
)
THEMES = {"ai": "#ArtificialIntelligence", "planet": "#EarthScience",
          "biology": "#Biology", "future-tech": "#FutureTechnology", "curiosity": "#ScienceFacts", "space": "#Space"}


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


def title(script: dict) -> str:
    """Keep the factual promise; remove clutter rather than invent clickbait."""
    text = re.sub(r"#\w+", "", script.get("title", "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:100].rstrip()


def tags(script: dict) -> list[str]:
    """Replace unrelated channel-wide defaults with a small topic-specific set."""
    chosen = [title(script).rstrip("?!.")]
    chosen += [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", h[1:]) for h in hashtags(script)]
    result = []
    for tag in chosen:
        if tag and tag.casefold() not in {t.casefold() for t in result}:
            if sum(len(t) + 3 for t in result) + len(tag) + 3 <= 500:
                result.append(tag)
    return result


def description(script: dict, cfg: dict) -> str:
    """Lead with the video's actual subject and preserve attribution/disclosure."""
    credits = script.get("_credits") or []
    credit_block = ("\n\nPhoto credits:\n" + "\n".join(f"- {c}" for c in credits)) if credits else ""
    return f"{title(script)}\n\n{' '.join(script.get('sentences', []))}\n\n{cfg['description_footer']}{credit_block}\n\n{' '.join(hashtags(script))}"[:4900]