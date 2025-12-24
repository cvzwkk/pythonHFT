sudo apt install libwebsockets-dev libssl-dev
gcc bitfinex_paper_bot.c -O3 -march=native \
    -mavx -mavx2 -mfma -mavx512f -mavx512dq \
    -lwebsockets -lssl -lcrypto -lm \
    -o bitfinex_bot
