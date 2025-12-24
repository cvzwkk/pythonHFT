sudo apt install libwebsockets-dev libssl-dev
gcc bitfinex_paper_bot.c -O3 -march=native \
    -mavx -mavx2 -mfma \
    -lwebsockets -lssl -lcrypto -lm \
    -o bitfinex_bot
