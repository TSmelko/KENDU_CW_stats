from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from requests import get
import matplotlib
matplotlib.use('Agg') # Non-GUI Backend for Replit
from matplotlib import pyplot as plt
import matplotlib.image as mpimg
import matplotlib.dates as mdates
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.ticker import StrMethodFormatter
from datetime import datetime, timedelta
import io
import base64
import os

ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY') # Get Etherscan API key from Secrets folder in Replit
ADDRESS_LINK = "https://etherscan.io/address/0xd22849fcb4c83389e65a1c40748a9b67157638a3"  # Used in sending message with graph
ADDRESS = "0xD22849fcB4C83389E65a1c40748a9b67157638A3"  # COMMUNITY WALLET
CONTRACTADDRESS = "0xaa95f26e30001251fb905d264Aa7b00eE9dF6C18"  # KENDU CA
BASE_URL = "https://api.etherscan.io/api"
ETHER_VALUE = 10 ** 18

# CoinGecko API for Token Price per coin
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses=0xaa95f26e30001251fb905d264Aa7b00eE9dF6C18&vs_currencies=usd"

# Telegram bot token
TELEGRAM_API_TOKEN = os.environ.get('TELEGRAM_API_TOKEN') # Get TG API key from Secrets folder in Replit

# API calls to Etherscan
def make_api_url(module, action, contractaddress, address, **kwargs):
    url = BASE_URL + f"?module={module}&action={action}&contractaddress={contractaddress}&address={address}&apikey={ETHERSCAN_API_KEY}"
    for key, value in kwargs.items():
        url += f"&{key}={value}"
    return url

# Current Kendu price in USD from CoinGecko
def fetch_kendu_price(contractaddress):
    response = get(COINGECKO_API.format(contractaddress))
    data = response.json()
    price = data.get(contractaddress.lower(), {}).get("usd", 0)
    formatted_price = f"{price:,.8f}".replace('.', ',')
    return price

# Kendu token balance
def get_kendu_balance(address, contractaddress):
    get_balance_url = make_api_url("account", "tokenbalance", CONTRACTADDRESS, ADDRESS, tag="latest")
    response = get(get_balance_url)
    data = response.json()
    value = int(data["result"]) / ETHER_VALUE
    return value

# Get transactions and plot the graph
async def get_graph(update: Update, context: CallbackContext):

    # Get the chat_id of the user who triggered the command / chat_id of the current user
    chat_id = update.effective_chat.id

    # Get the message ID of the original message, so we can reply to it
    message_id = update.message.message_id

    transactions_url = make_api_url("account", "tokentx", CONTRACTADDRESS, ADDRESS, startblock=0, endblock=99999999, page=1, offset=10000, sort="asc")
    response = get(transactions_url)
    data = response.json()["result"]

    internal_tx_url = make_api_url("account", "txlistinternal", CONTRACTADDRESS, ADDRESS, startblock=0, endblock=99999999, page=1, offset=10000, sort="asc")
    response2 = get(internal_tx_url)
    data2 = response2.json()["result"]

    data.extend(data2)
    data.sort(key=lambda x: int(x["timeStamp"]))

    kendu_price = fetch_kendu_price(CONTRACTADDRESS)
    if kendu_price == 0:
        print("KENDU GOT RUGGED.")
        return

    current_balance = 0
    balances = []
    usd_values = []
    times = []

    # Calculate the date 3 months ago
    three_months_ago = datetime.now() - timedelta(days=90)  

    for tx in data:
        to = tx["to"]
        from_addr = tx["from"]
        value = int(tx["value"]) / ETHER_VALUE

        if "gasPrice" in tx:
            gas = int(tx["gasUsed"]) * int(tx["gasPrice"]) / ETHER_VALUE
        else:
            gas = int(tx["gasUsed"]) / ETHER_VALUE

        time = datetime.fromtimestamp(int(tx["timeStamp"]))

        if time < three_months_ago:
            continue

        money_in = to.lower() == ADDRESS.lower()

        if money_in:
            current_balance += value
        else:
            current_balance -= value + gas

        total_kendu_value_usd = current_balance * kendu_price

        balances.append(current_balance)
        usd_values.append(total_kendu_value_usd)
        times.append(time)


    # Create plot
    plt.figure(figsize=(9, 5))
    plt.plot(times, balances, label="Kendu Token Balance", color="#EA674B", linewidth=3)

    # Format X axis label to dd mm format
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    plt.ylabel("KENDU Tokens")
    plt.title(f"Community Wallet Balance          Total Price: ${total_kendu_value_usd:,.2f}", fontsize=16, x=0.5, y=1.03)
    plt.grid(True)
    #plt.xticks(rotation=45)  # Rotate X axis Date
    plt.gca().yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.2)
    plt.tight_layout()

    # Load image from Replit file system
    logo_path = "KENDU_logo.png"
    if os.path.exists(logo_path):
        logo = mpimg.imread(logo_path)

        # Create OffsetImage + add to plot center
        imagebox = OffsetImage(logo, zoom=1.10, alpha=0.5)
        x_center = times[len(times) // 2]
        y_center = sum(balances) / len(balances)

        # Adjust Y position of Logo
        y_center *= 0.75  # Move Up/Down

        # Adjust X position of Logo
        x_center_num = mdates.date2num(x_center)
        x_center_num -= 2  # Move Left,  do += to move Right
        x_center = mdates.num2date(x_center_num)


        ab = AnnotationBbox(imagebox, (x_center, y_center), frameon=False)
        plt.gca().add_artist(ab)

    # Save as PNG
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)

    # Convert to base64 for sending to Telegram
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')

    # Send the graph and the message in one reply to the original message
    await context.bot.send_photo(chat_id=chat_id, photo=img, caption=ADDRESS_LINK, reply_to_message_id=message_id)

def main():
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("cw", get_graph))

    application.run_polling()

if __name__ == '__main__':
    main()