/*
 * Bitfinex 1s Paper Trading Bot
 * C + libwebsockets + AVX-ready
 *
 * gcc bitfinex_paper_bot.c -O3 -march=native \
 *   -mavx -mavx2 -mfma \
 *   -lwebsockets -lssl -lcrypto -lm -o bitfinex_bot
 */

#include <libwebsockets.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <time.h>
#include <math.h>

#define MAX_ORDERS 3
#define BASE_SIZE  0.001
#define SYMBOL     "tBTCUSD"

static int force_exit = 0;

/* =========================
   STRUCTURES
   ========================= */

typedef struct {
    double price;
    double size;
} Order;

typedef struct {
    Order orders[MAX_ORDERS];
    int count;
    int side;               // 1=LONG -1=SHORT
    double avg_price;
    double total_size;
} Position;

typedef struct {
    double balance;
    double unrealized;
    double realized;
} Account;

/* =========================
   GLOBAL STATE
   ========================= */

static double last_price = 0.0;
static double ema_fast = 0.0;
static double ema_slow = 0.0;
static time_t last_tick = 0;

static Position position = {0};
static Account  account  = {10000.0, 0.0, 0.0};

/* =========================
   SIGNAL HANDLER
   ========================= */

static void sigint_handler(int sig) {
    force_exit = 1;
}

/* =========================
   INDICATORS
   ========================= */

static inline double ema(double price, double prev, double alpha) {
    return alpha * price + (1.0 - alpha) * prev;
}

static inline double signal_predict(double price) {
    ema_fast = ema(price, ema_fast, 0.20);
    ema_slow = ema(price, ema_slow, 0.05);
    return ema_fast - ema_slow;
}

/* =========================
   POSITION HELPERS
   ========================= */

static inline double calc_pnl(double price) {
    if (position.count == 0) return 0.0;
    if (position.side == 1)
        return (price - position.avg_price) / position.avg_price;
    else
        return (position.avg_price - price) / position.avg_price;
}

static void add_order(double price, double size) {
    if (position.count >= MAX_ORDERS) return;

    Order *o = &position.orders[position.count];
    o->price = price;
    o->size  = size;

    position.avg_price =
        (position.avg_price * position.total_size + price * size) /
        (position.total_size + size);

    position.total_size += size;
    position.count++;
}

static void close_position(double price) {
    double pnl = calc_pnl(price);
    double profit = pnl * position.total_size * price;

    account.balance += profit;
    account.realized += profit;
    account.unrealized = 0.0;

    memset(&position, 0, sizeof(position));
}

/* =========================
   TRADING LOGIC (1 SECOND)
   ========================= */

static void trading_step(double price) {
    double sig = signal_predict(price);
    double pnl = calc_pnl(price);

    /* ENTRY */
    if (position.count == 0) {
        if (sig > 0.0) {
            position.side = 1;
            add_order(price, BASE_SIZE);
        } else if (sig < 0.0) {
            position.side = -1;
            add_order(price, BASE_SIZE);
        }
        return;
    }

    account.unrealized = pnl * position.total_size * price;

    /* TAKE PROFIT */
    if (pnl >= 0.00002) {
        close_position(price);
        return;
    }

    /* ADD MORE WHEN NEGATIVE */
    int level = (int)(-pnl / 0.00003);
    if (level >= position.count && position.count < MAX_ORDERS) {
        add_order(price, BASE_SIZE);
    }
}

/* =========================
   BITFINEX WS CALLBACK
   ========================= */

static int callback_bitfinex(
    struct lws *wsi,
    enum lws_callback_reasons reason,
    void *user, void *in, size_t len)
{
    switch (reason) {

    case LWS_CALLBACK_CLIENT_ESTABLISHED: {
        const char *sub =
            "{\"event\":\"subscribe\",\"channel\":\"ticker\",\"symbol\":\"" SYMBOL "\"}";
        lws_write(wsi,
            (unsigned char *)sub + LWS_PRE,
            strlen(sub),
            LWS_WRITE_TEXT);
        break;
    }

    case LWS_CALLBACK_CLIENT_RECEIVE: {
        const char *msg = (const char *)in;

        /* Ticker format:
           [CHANID, [ BID, BID_SIZE, ASK, ASK_SIZE, ... , LAST_PRICE ]]
        */
        double price = 0.0;
        if (sscanf(msg, "[%*d,[%*lf,%*lf,%*lf,%*lf,%*lf,%*lf,%lf", &price) == 1) {
            last_price = price;
        }
        break;
    }

    default:
        break;
    }
    return 0;
}

/* =========================
   PROTOCOLS
   ========================= */

static struct lws_protocols protocols[] = {
    {
        "bitfinex",
        callback_bitfinex,
        0,
        4096,
    },
    { NULL, NULL, 0, 0 }
};

/* =========================
   MAIN
   ========================= */

int main(void) {
    signal(SIGINT, sigint_handler);

    struct lws_context_creation_info info;
    memset(&info, 0, sizeof(info));

    info.port = CONTEXT_PORT_NO_LISTEN;
    info.protocols = protocols;
    info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;

    struct lws_context *context = lws_create_context(&info);
    if (!context) {
        fprintf(stderr, "lws init failed\n");
        return 1;
    }

    struct lws_client_connect_info ccinfo = {0};
    ccinfo.context = context;
    ccinfo.address = "api-pub.bitfinex.com";
    ccinfo.port = 443;
    ccinfo.path = "/ws/2";
    ccinfo.host = ccinfo.address;
    ccinfo.origin = ccinfo.address;
    ccinfo.ssl_connection = LCCSCF_USE_SSL;
    ccinfo.protocol = protocols[0].name;

    if (!lws_client_connect_via_info(&ccinfo)) {
        fprintf(stderr, "connection failed\n");
        return 1;
    }

    printf("Bitfinex paper trading bot started\n");

    while (!force_exit) {
        lws_service(context, 0);

        time_t now = time(NULL);
        if (now != last_tick && last_price > 0.0) {
            last_tick = now;
            trading_step(last_price);

            printf(
                "%s | Price %.2f | Pos %d | Orders %d | Avg %.2f | PnL %.4f%% | Bal %.2f\r",
                SYMBOL,
                last_price,
                position.side,
                position.count,
                position.avg_price,
                calc_pnl(last_price) * 100.0,
                account.balance
            );
            fflush(stdout);
        }
    }

    lws_context_destroy(context);
    printf("\nShutdown\n");
    return 0;
}
