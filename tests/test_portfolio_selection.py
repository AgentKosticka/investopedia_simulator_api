import unittest
from types import SimpleNamespace
from unittest.mock import patch

from investopedia_api import InvestopediaApi


def portfolio(name, game_id, portfolio_id):
    return SimpleNamespace(
        game_name=name,
        game_id=game_id,
        portfolio_id=portfolio_id,
    )


class PortfolioSelectionTests(unittest.TestCase):
    def setUp(self):
        self.portfolios = [
            portfolio("Default Game", "game-1", "portfolio-1"),
            portfolio("Custom Game", "game-2", "portfolio-2"),
        ]

    def make_client(self, **kwargs):
        with patch("investopedia_api.Session.login"), patch(
            "investopedia_api.Parsers.get_portfolios",
            return_value=self.portfolios,
        ):
            return InvestopediaApi({"access_token": "test"}, **kwargs)

    def test_selects_game_name(self):
        client = self.make_client(game_name="Custom Game")
        self.assertEqual(client.portfolio.portfolio_id, "portfolio-2")

    def test_selects_game_id_beyond_first_portfolio(self):
        client = self.make_client(game_id="game-2")
        self.assertEqual(client.portfolio.portfolio_id, "portfolio-2")

    def test_selects_portfolio_id(self):
        client = self.make_client(portfolio_id="portfolio-2")
        self.assertEqual(client.portfolio.game_name, "Custom Game")

    def test_rejects_multiple_selectors(self):
        with self.assertRaises(ValueError):
            self.make_client(game_name="Custom Game", game_id="game-2")


if __name__ == "__main__":
    unittest.main()
