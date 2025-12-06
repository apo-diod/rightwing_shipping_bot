# rightwing_shipping_bot
A silly little bot to ship people in Telegram

docker build . --tag rightwingbot:latest
docker run --env TG_TOKEN="YOUR_TG_TOKEN" -v /opt/bots/data:/opt/bot/data -d rightwingbot:latest