import pytest

from mootlib.scrapers.gjopen import GJOpenAnswer, GJOpenMarket, GoodJudgmentOpenScraper


@pytest.mark.asyncio
async def test_gjopen_market_creation():
    """Test creation of GJOpen market from sample data."""
    sample_data = {
        "id": 123,
        "name": "Test Question",
        "published_at": "2024-01-01T00:00:00Z",
        "predictors_count": 50,
        "comments_count": 10,
        "description": "Test description",
        "binary?": True,
        "continuous_scored?": False,
        "type": "binary",
        "answers": [
            {"name": "Yes", "probability": 0.7},
            {"name": "No", "probability": 0.3},
        ],
    }

    market = GJOpenMarket.from_gjopen_question_data(
        sample_data, "https://example.com/test"
    )
    assert market is not None
    assert market.id == "gjopen_123"
    assert market.question == "Test Question"
    assert market.predictors_count == 50
    assert len(market.outcomes) == 2
    assert market.outcomes[0].probability == 0.7


@pytest.mark.asyncio
async def test_pooled_market_conversion():
    """Test conversion from GJOpen market to pooled market."""
    market = GJOpenMarket(
        id="gjopen_123",
        question="Test Question",
        published_at="2024-01-01T00:00:00Z",
        predictors_count=50,
        comments_count=10,
        description="Test description",
        binary=True,
        continuous_scored=False,
        outcomes=[
            GJOpenAnswer(name="Yes", probability=0.7),
            GJOpenAnswer(name="No", probability=0.3),
        ],
        formatted_outcomes="Yes: 70.0%; No: 30.0%",
        url="https://example.com/test",
        q_type="binary",
    )

    pooled = market.to_pooled_market()
    assert pooled.id == "gjopen_123"
    assert pooled.question == "Test Question"
    assert pooled.n_forecasters == 50
    assert len(pooled.outcomes) == 2
    assert pooled.outcome_probabilities[0] == 0.7
