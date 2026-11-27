"""Free deterministic photo plans for narration without stored scene searches."""
import re

from . import visuals

SUBJECTS = (
    (r"\b(?:arm|limb|hand|finger)s?\b", "human hand"),
    (r"\b(?:regenerat\w*|tissue|nerve|blood|liver|medicine|wound)\b", "medical laboratory"),
    (r"\b(?:dna|gene|cell)s?\b", "biology laboratory"),
    (r"\b(?:battery|charging|electricity)\b", "battery"),
    (r"\b(?:humanoid|robot)s?\b", "robot"),
    (r"\b(?:ai|computer|algorithm|language model|machine learning)\b", "computer"),
    (r"\b(?:headset|virtual reality|vr)\b", "virtual reality headset"),
    (r"\b(?:cable|internet|network)s?\b", "network cable"),
    (r"\b(?:ocean|seawater|sea)\b", "ocean"),
    (r"\b(?:phone|smartphone|device)s?\b", "smartphone"),
    (r"\b(?:scientist|researcher|experiment)s?\b", "science laboratory"),
)
STOP = {"what", "why", "how", "can", "could", "would", "does", "do", "is", "are",
        "if", "we", "you", "your", "it", "the", "a", "an", "to", "of", "in",
        "and", "for", "with", "than", "more", "whole", "really", "happens"}


def ensure(script: dict) -> None:
    """Fill only missing queries; preserve explicit plans and NASA subject routing."""
    sentences = script["sentences"]
    existing = script.get("photos") or []
    vs = script.get("visuals") or []
    photos = []
    for i, sentence in enumerate(sentences):
        photo = existing[i] if i < len(existing) else None
        visual = vs[i] if i < len(vs) else None
        resolved = visuals.matching_photo(sentence, visual, photo, script["title"])
        if resolved:
            photos.append(resolved)
            continue
        context = visual or sentence
        query = next((q for pattern, q in SUBJECTS if re.search(pattern, context, re.I)), None)
        if query is None:
            query = next((q for pattern, q in SUBJECTS if re.search(pattern, script["title"], re.I)), None)
        if query is None:
            words = re.findall(r"[a-zA-Z]+", visual or script["title"])
            query = " ".join(w for w in words if w.lower() not in STOP)[:100]
        photos.append({"source": "pexels", "query": query or "science laboratory"})
    script["photos"] = photos