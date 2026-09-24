from trade_common import Expiration, OrderLimit, TransactionType, OptionTrade, StockTrade
from api_models import OptionChain, Parsers, stock_quote, OptionScope
from session_singleton import Session
import warnings


class InvestopediaApi(object):
    def __init__(
        self,
        auth=None,
        game_name=None,
        portfolio_id=None,
        game_id=None,
        auth_file=None,
    ):
        Session.login(auth, auth_file=auth_file)
        self.portfolios = Parsers.get_portfolios()

        if not self.portfolios:
            raise RuntimeError(
                "No active Investopedia Simulator portfolios were returned for this account."
            )

        self.portfolio = self.portfolios[0]

        if game_name is not None or portfolio_id is not None or game_id is not None:
            self.change_portfolio(
                game_name=game_name,
                game_id=game_id,
                portfolio_id=portfolio_id,
            )

        print(
            "Initialized portfolio ID %s in game %s"
            % (self.portfolio.portfolio_id, self.portfolio.game_name)
        )

    def change_portfolio(self, game_name=None, game_id=None, portfolio_id=None):
        selectors = [
            game_name is not None,
            game_id is not None,
            portfolio_id is not None,
        ]

        if sum(selectors) == 0:
            warnings.warn(
                "Portfolio not changed; specify game_name, game_id, or portfolio_id."
            )
            return False

        if sum(selectors) > 1:
            raise ValueError(
                "Specify exactly one of game_name, game_id, or portfolio_id."
            )

        for portfolio in self.portfolios:
            matches = (
                (game_name is not None and portfolio.game_name == game_name)
                or (
                    game_id is not None
                    and str(portfolio.game_id) == str(game_id)
                )
                or (
                    portfolio_id is not None
                    and str(portfolio.portfolio_id) == str(portfolio_id)
                )
            )

            if matches:
                self.portfolio = portfolio
                print(
                    "Changed portfolio to portfolio ID %s in game %s"
                    % (self.portfolio.portfolio_id, self.portfolio.game_name)
                )
                return True

        selector_name = (
            "game_name"
            if game_name is not None
            else "game_id"
            if game_id is not None
            else "portfolio_id"
        )
        selector_value = (
            game_name
            if game_name is not None
            else game_id
            if game_id is not None
            else portfolio_id
        )
        warnings.warn(
            "Portfolio not changed, could not find portfolio with %s %s"
            % (selector_name, selector_value)
        )
        return False

    def refresh_portfolio(self):
        current_portfolio_id = self.portfolio.portfolio_id
        self.portfolios = Parsers.get_portfolios()

        for portfolio in self.portfolios:
            if str(current_portfolio_id) == str(portfolio.portfolio_id):
                self.portfolio = portfolio
                return self.portfolio

        raise RuntimeError(
            "The selected portfolio %s is no longer present in the active games list."
            % current_portfolio_id
        )

    @staticmethod
    def get_option_chain(symbol):
        return OptionChain(symbol)

    @staticmethod
    def get_stock_quote(symbol):
        return stock_quote(symbol)


class StockTrade(StockTrade):
    pass


class OptionTrade(OptionTrade):
    pass


class Expiration(Expiration):
    pass


class OrderLimit(OrderLimit):
    pass


class TransactionType(TransactionType):
    pass


class OptionChain(OptionChain):
    pass


class OptionScope(OptionScope):
    pass
