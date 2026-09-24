# Investopedia Simulator API

Python client for Investopedia's Stock Simulator GraphQL backend.

This fork updates the original project for Investopedia's current **passwordless** authentication flow and fixes custom-game portfolio selection.

## Features

- Read active simulator games and portfolios
- Select a game by name, game ID, or portfolio ID
- Read stock, short, and option positions
- Read/cancel pending orders
- Buy and sell stocks
- Short and cover stocks
- Read option chains and trade options
- Reuse/refresh OIDC bearer tokens for headless operation

## Authentication

Investopedia no longer uses the username/password flow that the original project automated with Puppeteer. This fork authenticates with the bearer tokens issued to a normal signed-in Investopedia Simulator session.

### Recommended: environment variables

Sign in to the Investopedia Simulator in your browser. In Developer Tools -> Network, inspect the simulator's authentication traffic. The token response from the Investopedia OpenID Connect endpoint contains an `access_token` and, when issued, a `refresh_token`.

Set:

```bash
export INVESTOPEDIA_ACCESS_TOKEN="..."
export INVESTOPEDIA_REFRESH_TOKEN="..."
```

On PowerShell:

```powershell
$env:INVESTOPEDIA_ACCESS_TOKEN="..."
$env:INVESTOPEDIA_REFRESH_TOKEN="..."
```

Then:

```python
from investopedia_api import InvestopediaApi

client = InvestopediaApi()
```

The refresh token is optional. With an access token only, the API works until that token expires. With a refresh token, the client refreshes the access token when required and persists rotated tokens to the ignored `auth.json` file.

### JSON authentication

You can also pass the token data directly:

```python
from investopedia_api import InvestopediaApi

auth = {
    "access_token": "...",
    "refresh_token": "...",  # optional
}

client = InvestopediaApi(auth)
```

Or place the same object in `auth.json` in the repository directory and call:

```python
client = InvestopediaApi()
```

Do not commit tokens. `auth.json` and `credentials.json` are ignored by Git.

## Custom games

The account's active simulator portfolios are discovered through Investopedia's GraphQL API.

List them:

```python
client = InvestopediaApi()

for portfolio in client.portfolios:
    print(portfolio.game_name, portfolio.game_id, portfolio.portfolio_id)
```

Select by game name:

```python
client = InvestopediaApi(game_name="My custom game")
```

Or by ID:

```python
client = InvestopediaApi(game_id="...")
client = InvestopediaApi(portfolio_id="...")
```

You can switch after startup:

```python
client.change_portfolio(game_name="Another game")
```

Only active games returned for the signed-in Investopedia account can be selected.

## Example trade

```python
from investopedia_api import InvestopediaApi, StockTrade, TransactionType

client = InvestopediaApi(game_name="My custom game")
portfolio = client.portfolio

trade = StockTrade(
    portfolio_id=portfolio.portfolio_id,
    symbol="AAPL",
    quantity=1,
    transaction_type=TransactionType.BUY,
)

trade.validate()
trade.execute()
```

## Installation

```bash
git clone https://github.com/AgentKosticka/investopedia_simulator_api.git
cd investopedia_simulator_api
pip install -r requirements.txt
```

Node.js/Puppeteer is no longer required for normal operation.

## Notes

This is an unofficial client for Investopedia's internal simulator API. Investopedia can change the GraphQL schema, authentication flow, or endpoints without notice.
