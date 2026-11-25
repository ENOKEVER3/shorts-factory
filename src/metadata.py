"""Small, topic-matched hashtag sets for bank and generated Shorts."""
import re
from . import trends

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
    (r"\b(nasa|voyager|space station|astronaut|satellite|satellites)\b", "#NASA"),
    (r"\b(point nemo|island|trench|remote|loneliest)\b", "#RemotePlaces"),
    (r"\b(ocean|deep sea|submarine)\b", "#Ocean"),
    (r"\b(escape|escaped|breakout)\b", "#PrisonEscape"),
    (r"\b(heist|robbery|stole)\b", "#Heist"),
    (r"\b(con artist|impostor|fraud)\b", "#ConArtist"),
)
CHANNEL_KEYWORDS = {
    "": ["what would happen if", "space facts", "science explained"],
    "uriel": ["true crime", "famous escapes", "true story"],
}
THEMES = {"ai": "#ArtificialIntelligence", "planet": "#EarthScience",
          "biology": "#Biology", "future-tech": "#FutureTechnology", "curiosity": "#ScienceFacts", "space": "#Space", "founders": "#TechHistory",
          "escape": "#PrisonEscape", "heist": "#Heist", "con-artist": "#ConArtist", "case-mystery": "#TrueCrime"}
CRIME_THEMES = {"escape", "heist", "con-artist", "case-mystery", "crime"}


def _brand() -> str:
    import os
    return "#Uriel" if os.environ.get("SF_PROFILE", "").strip() == "uriel" else "#MAKOKOGW"


def hashtags(script: dict) -> list[str]:
    """Prioritize the title, then narration; never carry stale creator/trend tags."""
    selected = []
    for text in (script.get("title", ""), " ".join(script.get("sentences", []))):
        for pattern, tag in TOPICS:
            if re.search(pattern, text, re.IGNORECASE) and tag not in selected:
                selected.append(tag)
    crime = script.get("theme") in CRIME_THEMES
    theme = THEMES.get(script.get("theme"), "#TrueCrime" if crime else "#Science")
    if crime:
        selected = [t for t in selected if "Science" not in t]
    if theme not in selected:
        selected.insert(0, theme) if crime else selected.append(theme)
    if crime and "#TrueCrime" not in selected:
        selected.append("#TrueCrime")
    matching = [t['hashtag'] for t in trends.matches(script)]
    selected = list(dict.fromkeys([*matching, *selected]))
    return [*selected[:3], "#Shorts", _brand()]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"#\w+", "", text or "")).strip()


def title(script: dict) -> str:
    """Phrase titles like real searches ("What would happen if…", "Why…") without inventing claims."""
    text = _clean(script.get("search_title") or script.get("title", ""))
    text = re.sub(r"^what if\b", "What would happen if", text, flags=re.IGNORECASE)
    text = text[:100].rstrip()
    matching = trends.matches(script)
    if matching:
        suffix = ' ' + matching[0]['hashtag']
        if len(text) + len(suffix) <= 100:
            text += suffix
    return text


def search_queries(script: dict) -> list[str]:
    """Lowercase query-style phrasings viewers type into YouTube/Google search."""
    base = _clean(title(script)).rstrip("?!.").strip()
    low = base[0].lower() + base[1:] if base else ""
    out = [low.lower()]
    m = re.match(r"what would happen if (.+)", low, re.IGNORECASE)
    if m:
        out += [f"what happens if {m.group(1)}", f"what if {m.group(1)}"]
    m = re.match(r"why (.+)", low, re.IGNORECASE)
    if m:
        out.append(f"{m.group(1)} explained")
    m = re.match(r"how (.+)", low, re.IGNORECASE)
    if m:
        out.append(f"how {m.group(1)} explained")
    seen, result = set(), []
    for q in out:
        q = q.strip().lower()
        if q and q not in seen:
            seen.add(q); result.append(q)
    return result[:3]


def tags(script: dict) -> list[str]:
    """Replace unrelated channel-wide defaults with a small topic-specific set."""
    chosen = [*search_queries(script)]
    chosen += [_clean(str(t)) for t in (script.get("tags") or [])]
    chosen += [t['query'] for t in trends.matches(script)]
    chosen += [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", h[1:]) for h in hashtags(script)]
    import os
    chosen += CHANNEL_KEYWORDS.get(os.environ.get("SF_PROFILE", "").strip(), CHANNEL_KEYWORDS[""])
    result = []
    for tag in chosen:
        if tag and tag.casefold() not in {t.casefold() for t in result}:
            if len(result) < 30 and sum(len(t) + 3 for t in result) + len(tag) + 3 <= 500:
                result.append(tag)
    return result


def description(script: dict, cfg: dict) -> str:
    """Lead with the video's actual subject and preserve attribution/disclosure."""
    credits = script.get("_credits") or []
    credit_block = ("\n\nPhoto credits:\n" + "\n".join(f"- {c}" for c in credits)) if credits else ""
    lead = _clean(title(script))
    if not lead.endswith(("?", ".", "!")):
        question = re.match(r"(why|what)\b", lead, re.IGNORECASE) or re.match(r"how (do|does|did|can|is|are|much|many|long|far)\b", lead, re.IGNORECASE)
        lead += "?" if question else "."
    return f"{lead} Here is the short answer.\n\n{' '.join(script.get('sentences', []))}\n\n{cfg['description_footer']}{credit_block}\n\n{' '.join(hashtags(script))}"[:4900]