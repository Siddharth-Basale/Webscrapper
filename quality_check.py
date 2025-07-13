# quality_check.py
def validate_summary_quality(location):
    checklist = [
        ("Hook present in first 10 words", lambda s: len(s.split()) >= 10),
        ("Contains at least 2 citations", lambda s: s.count('[') >= 2),
        ("Balanced perspective", lambda s: "but" in s or "however" in s)
    ]
    
    score = 0
    for (criteria, test) in checklist:
        if test(location['summary']):
            score += 1
    
    location['quality_score'] = (score / len(checklist)) * 100
    return location