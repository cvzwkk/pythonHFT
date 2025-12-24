/*
 * Bitfinex 1s Paper Trading Bot
 * C + libwebsockets
 * Lock-free ring buffer
 * Monotonic clock
 * WS thread separated
 *
 * BUILD:
 * gcc bitfinex_paper_bot.c -O3 -march=native \
 *   -mavx -mavx2 -mfma \
 *   -lwebsockets -lssl -lcrypto -lm -lpthread \
 *   -o bitfinex_bot
 */

#include <libwebsockets.h>
#include <pthread.h>
#include <signal.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <stdatomic.h>

/* ================= CONFIG ================= */

#define SYMBOL       "tBTCUSD"
#define BASE_SIZE    0.001
#define MAX_ORDERS   3

#define TP_PNL       0.00002
#define ADD_PNL      0.00003

#define RING_SIZE    1024

/* ================= UTIL ================= */

static inline uint64_t mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

/* ================= RING BUFFER ================= */

typedef struct {
    double price;
    uint64_t ts;
} Tick;

static Tick ring[RING_SIZE];
static atomic_uint write_idx = 0;
static atomic_uint read_idx  = 0;

static inline void ring_push(double price, uint64_t ts) {
    unsigned w = atomic_load_explicit(&write_idx, memory_order_relaxed);
    ring[w % RING_SIZE] = (Tick){price, ts};
    atomic_store_explicit(&write_idx, w + 1, memory_order_release);
}

static inline int ring_pop(Tick *out) {
    unsigned r = atomic_load_explicit(&read_idx, memory_order_relaxed);
    unsigned w = atomic_load_explicit(&write_idx, memory_order_acquire);
    if (r == w) return 0;
    *out = ring[r % RING_SIZE];
    atomic_store_explicit(&read_idx, r + 1, memory_order_release);
    return 1;
}

/* ================= TRADING STATE ================= */

typedef struct {
    double price;
    double size;
} Order;

typedef struct {
    Order orders[MAX_ORDERS];
    int count;
    int side;           /* 1 LONG, -1 SHORT */
    double avg_price;
    double total_size;
} Position;

typedef struct {
    double balance;
    double realized;
    double unrealized;
} Account;

static Position pos = {0};
static Account  acc = {10000.0, 0.0, 0.0};

/* ================= INDICATORS ================= */

static double ema_fast = 0.0;
static double ema_slow = 0.0;
static double last_price = 0.0;

static inline double ema(double x, double prev, double a) {
    return a * x + (1.0 - a) * prev;
}

static inline double predict(double price) {
    ema_fast = ema(price, ema_fast, 0.20);
    ema_slow = ema(price, ema_slow, 0.05);
    return ema_fast - ema_slow;
}

/* ================= TRADING LOGIC ================= */

static inline double calc_pnl(double price) {
    if (pos.count == 0) return 0.0;
    if (pos.side == 1)
        return (price - pos.avg_price) / pos.avg_price;
    else
        return (pos.avg_price - price) / pos.avg_price;
}

static void add_order(double price) {
    if (pos.count >= MAX_ORDERS) return;

    double size = BASE_SIZE;
    pos.avg_price =
        (pos.avg_price * pos.total_size + price * size) /
        (pos.total_size + size);

    pos.orders[pos.count++] = (Order){price, size};
    pos.total_size += size;
}

static void close_position(double price) {
    double pnl = calc_pnl(price);
    double profit = pnl * pos.total_size * price;
    acc.balance += profit;
    acc.realized += profit;
    acc.unrealized = 0.0;
    memset(&pos, 0, sizeof(pos));
}

static void trading_step(double price) {
    double sig = predict(price);
    double pnl = calc_pnl(price);

    if (pos.count == 0) {
        if (sig > 0) { pos.side = 1; add_order(price); }
        else if (sig < 0) { pos.side = -1; add_order(price); }
        return;
    }

    acc.unrealized = pnl * pos.total_size * price;

    if (pnl >= TP_PNL) {
        close_position(price);
        return;
    }

    int level = (int)(-pnl / ADD_PNL);
    if (level >= pos.count && pos.count < MAX_ORDERS)
        add_order(price);
}

/* ================= JSON PRICE PARSER ================= */

static inline int parse_price(const char *s, double *out) {
    int commas = 0;
    while (*s) {
        if (*s == ',') commas++;
        if (commas == 6) {
            *out = strtod(s + 1, NULL);
            return 1;
        }
        s++;
    }
    return 0;
}

/* ================= WEBSOCKET ================= */

static int force_exit = 0;

static int ws_cb(struct lws *wsi,
    enum lws_callback_reasons reason,
    void *user, void *in, size_t len)
{
    switch (reason) {

    case LWS_CALLBACK_CLIENT_ESTABLISHED: {
        unsigned char buf[LWS_PRE + 128];
        const char *sub =
            "{\"event\":\"subscribe\",\"channel\":\"ticker\",\"symbol\":\"" SYMBOL "\"}";
        size_t l = strlen(sub);
        memcpy(buf + LWS_PRE, sub, l);
        lws_write(wsi, buf + LWS_PRE, l, LWS_WRITE_TEXT);
        break;
    }

    case LWS_CALLBACK_CLIENT_RECEIVE: {
        const char *msg = (const char *)in;
        if (msg[0] != '[' || strstr(msg, "\"hb\"")) break;

        double price;
        if (parse_price(msg, &price)) {
            ring_push(price, mono_ns());
        }
        break;
    }

    default:
        break;
    }
    return 0;
}

static struct lws_protocols protocols[] = {
    { "bitfinex", ws_cb, 0, 4096 },
    { NULL, NULL, 0, 0 }
};

/* ================= THREADS ================= */

static void *ws_thread(void *arg) {
    struct lws_context *ctx = arg;
    while (!force_exit)
        lws_service(ctx, 0);
    return NULL;
}

static void *trade_thread(void *arg) {
    uint64_t last = 0;
    Tick t;

    while (!force_exit) {
        if (ring_pop(&t)) {
            last_price = t.price;
        }

        uint64_t now = mono_ns();
        if (last_price > 0 && now - last >= 1000000000ULL) {
            last = now;
            trading_step(last_price);

            double pnl_pct = calc_pnl(last_price) * 100.0;
            double pnl_val = acc.unrealized;

            printf(
                "%s | Price: %.2f | Orders: %d | Side: %s | Avg: %.2f | "
                "PnL: %.4f%% (%.2f) | Balance: %.2f\r",
                SYMBOL,
                last_price,
                pos.count,
                pos.side == 1 ? "LONG" : pos.side == -1 ? "SHORT" : "FLAT",
                pos.avg_price,
                pnl_pct,
                pnl_val,
                acc.balance
            );
            fflush(stdout);
        }
    }
    return NULL;
}

/* ================= MAIN ================= */

static void on_sig(int s) { force_exit = 1; }

int main(void) {
    signal(SIGINT, on_sig);

    struct lws_context_creation_info info = {0};
    info.port = CONTEXT_PORT_NO_LISTEN;
    info.protocols = protocols;
    info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;

    struct lws_context *ctx = lws_create_context(&info);
    if (!ctx) return 1;

    struct lws_client_connect_info cc = {0};
    cc.context = ctx;
    cc.address = "api-pub.bitfinex.com";
    cc.port = 443;
    cc.path = "/ws/2";
    cc.host = cc.address;
    cc.origin = cc.address;
    cc.ssl_connection = LCCSCF_USE_SSL;
    cc.protocol = protocols[0].name;

    if (!lws_client_connect_via_info(&cc)) return 1;

    pthread_t ws_t, tr_t;
    pthread_create(&ws_t, NULL, ws_thread, ctx);
    pthread_create(&tr_t, NULL, trade_thread, NULL);

    pthread_join(ws_t, NULL);
    pthread_join(tr_t, NULL);

    lws_context_destroy(ctx);
    return 0;
}
