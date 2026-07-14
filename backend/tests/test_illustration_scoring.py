from app.services.illustration_scoring import (
    ImageCandidate,
    merge_candidates,
    score_candidate,
    top_heuristic,
)


def test_fraction_illustration_scores_high():
    score = score_candidate(
        title="Обыкновенные дроби наглядно круг иллюстрация",
        page_url="https://example.com/fractions",
        image_url="https://example.com/img.png",
        topic="Обыкновенные дроби",
        subject="Математика",
        width=800,
        height=600,
    )
    assert score > 40


def test_presentation_slide_scores_low():
    score = score_candidate(
        title="Презентация обыкновенные дроби ppt слайд",
        page_url="https://ppt-online.org/slides",
        image_url="https://ppt-online.org/img.png",
        topic="Обыкновенные дроби",
        subject="Математика",
    )
    assert score < 0


def test_merge_deduplicates_urls():
    pool_a = [
        ImageCandidate("https://a.com/1.png", "Title A", "https://a.com", "web", 50),
        ImageCandidate("https://a.com/2.png", "Title B", "https://a.com", "web", 30),
    ]
    pool_b = [
        ImageCandidate("https://a.com/1.png", "Title A better", "https://a.com", "wiki", 70),
    ]
    merged = merge_candidates([pool_a, pool_b])
    urls = [c.image_url for c in merged]
    assert urls == ["https://a.com/1.png", "https://a.com/2.png"]
    assert merged[0].heuristic_score == 70
    assert merged[0].source == "wiki"


def test_historical_map_penalized_for_non_map_topic():
    score = score_candidate(
        title="Historical map of Russia 1917",
        page_url="https://example.com/map",
        image_url="https://example.com/map.png",
        topic="Февральская революция 1917",
        subject="История",
    )
    assert score < 20


def test_map_ok_for_geography():
    score = score_candidate(
        title="Political map of Europe",
        page_url="https://example.com/map",
        image_url="https://example.com/map.png",
        topic="Карта Европы",
        subject="География",
    )
    assert score >= 0


def test_top_heuristic_excludes_blocked():
    candidates = [
        ImageCandidate("https://a.com/1.png", "Good", "https://a.com", "web", 50),
        ImageCandidate("https://a.com/2.png", "Bad", "https://a.com", "web", -1000),
    ]
    top = top_heuristic(candidates, max_count=3)
    assert len(top) == 1
    assert top[0].image_url == "https://a.com/1.png"
