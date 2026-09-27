// Unit tests of the header-only C++ debt-dynamics engine, compiled without Python (see ../CMakeLists.txt).
//
// The Python test suite (tests/public_debt) compares the engine with NumPy reference implementations through the
// pybind11 bindings. These tests check the C++ code on its own, so that it can be built with strict warnings and
// run under AddressSanitizer, UndefinedBehaviorSanitizer and ThreadSanitizer:
// * published reference outputs of the random number generators;
// * exact identities of the debt accumulation equation (change in debt = snowball - primary balance + stock-flow
//   adjustment; the debt-stabilising primary balance; the closed form of the effective interest rate);
// * the stochastic DSA reduced to deterministic projections when the shocks are degenerate (VAR decay, rate floor,
//   fiscal reaction), and the frequencies of the residual bootstrap;
// * exact monotonicity of the adjustment grid, which reuses the same shocks for every adjustment;
// * results that must not depend on the number of threads;
// * argument validation.
// Statistical checks use four standard errors (two-sided type I error about 6e-5 each) with fixed seeds.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <vector>

#include "debt_dynamics.hpp"
#include "parallel.hpp"
#include "random.hpp"

namespace {

int g_checks = 0;
int g_failures = 0;

void report(bool ok, const char* what, const char* file, int line) {
    ++g_checks;
    if (!ok) {
        ++g_failures;
        std::fprintf(stderr, "%s:%d: check failed: %s\n", file, line, what);
    }
}

void report_close(double a, double b, double tol, const char* what, const char* file, int line) {
    const bool ok = std::isfinite(a) && std::isfinite(b) && std::abs(a - b) <= tol;
    report(ok, what, file, line);
    if (!ok) std::fprintf(stderr, "    %.17g vs %.17g (tolerance %.3g)\n", a, b, tol);
}

#define CHECK(cond) report((cond), #cond, __FILE__, __LINE__)
#define CHECK_CLOSE(a, b, tol) report_close((a), (b), (tol), #a " ~ " #b, __FILE__, __LINE__)

template <class Fn>
bool throws_invalid_argument(Fn&& fn) {
    try {
        fn();
    } catch (const std::invalid_argument&) {
        return true;
    } catch (...) {
        return false;
    }
    return false;
}

pd_engine::Baseline constant_baseline(std::size_t H, double g, double pi, double r, double pb, double sfa = 0.0) {
    pd_engine::Baseline b;
    b.growth.assign(H, g);
    b.inflation.assign(H, pi);
    b.market_rate.assign(H, r);
    b.primary_balance.assign(H, pb);
    b.sfa.assign(H, sfa);
    return b;
}

// Deterministic shocks: A = 0, u0 = 0 and a single residual row, so that u_t = e every year.
pd_engine::ShockModel fixed_shock(double eg, double epi, double er) {
    pd_engine::ShockModel m;
    m.A.assign(9, 0.0);
    m.u0.assign(3, 0.0);
    m.residuals = {eg, epi, er};
    return m;
}

// ------------------------------------------------------------------------------------------------ random numbers

void test_splitmix64_reference() {
    // Reference sequence of Vigna's splitmix64.c for the seed 1234567.
    std::uint64_t state = 1234567;
    const std::uint64_t expected[] = {6457827717110365317ULL, 3203168211198807973ULL, 9817491932198370423ULL,
                                      4593380528125082431ULL, 16408922859458223821ULL};
    for (std::uint64_t e : expected) CHECK(pd_engine::splitmix64(state) == e);
}

void test_xoshiro_streams() {
    // Values from a transcription of the reference xoshiro256** algorithm (Blackman and Vigna), with the state
    // seeded as in pd_engine::Xoshiro256; the transcription reproduces the published outputs from {1, 2, 3, 4}.
    pd_engine::Xoshiro256 a(42, 0), b(42, 7);
    const std::uint64_t ea[] = {17604071880264941726ULL, 13049929662915288091ULL, 16314220431934199612ULL,
                                16017857136869241811ULL};
    const std::uint64_t eb[] = {15260628496888913177ULL, 12080209494996618911ULL, 16192203974094658541ULL,
                                4943040130464974858ULL};
    for (int k = 0; k < 4; ++k) {
        CHECK(a.next() == ea[k]);
        CHECK(b.next() == eb[k]);
    }
}

void test_uniform_and_normal_moments() {
    const std::size_t n = 1000000;
    const double dn = static_cast<double>(n);
    pd_engine::Xoshiro256 rng(2026);
    double s = 0.0, q = 0.0, lo = 1.0, hi = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double u = rng.uniform();
        s += u;
        q += u * u;
        lo = std::min(lo, u);
        hi = std::max(hi, u);
    }
    CHECK(lo > 0.0 && hi < 1.0);  // open interval
    CHECK_CLOSE(s / dn, 0.5, 4.0 * std::sqrt(1.0 / 12.0 / dn));
    CHECK_CLOSE(q / dn - (s / dn) * (s / dn), 1.0 / 12.0, 4.0 * std::sqrt(1.0 / 180.0 / dn));
    pd_engine::Xoshiro256 g(7);
    double m = 0.0, v = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        const double z = g.normal();
        m += z;
        v += z * z;
    }
    m /= dn;
    v = v / dn - m * m;
    CHECK_CLOSE(m, 0.0, 4.0 / std::sqrt(dn));
    CHECK_CLOSE(v, 1.0, 4.0 * std::sqrt(2.0 / dn));
}

void test_parallel_for() {
    const std::size_t n = 1000;
    for (int threads : {1, 3, 8}) {
        std::vector<double> out(n, 0.0);
        pd_engine::parallel_for(n, threads, [&](std::size_t i) { out[i] = static_cast<double>(i) * static_cast<double>(i); });
        double total = 0.0;
        for (double v : out) total += v;
        CHECK(total == 332833500.0);  // sum of i^2 for i < 1000
    }
    bool rethrown = false;
    try {
        pd_engine::parallel_for(100, 4, [](std::size_t i) {
            if (i == 57) throw std::runtime_error("task failed");
        });
    } catch (const std::runtime_error&) {
        rethrown = true;
    }
    CHECK(rethrown);
}

// ------------------------------------------------------------------------------------------------ deterministic

void test_projection_identities() {
    // A varying baseline: the change in the debt ratio is exactly the snowball effect minus the primary balance
    // plus the stock-flow adjustment, and interest spending is d_{t-1} i_t / (1 + gamma_t).
    pd_engine::Baseline b;
    b.growth = {0.01, -0.02, 0.015, 0.007, 0.012};
    b.inflation = {0.02, 0.05, 0.03, 0.018, 0.02};
    b.market_rate = {0.035, 0.04, 0.038, 0.03, 0.032};
    b.primary_balance = {0.005, -0.03, 0.0, 0.01, 0.015};
    b.sfa = {0.002, 0.0, -0.004, 0.001, 0.0};
    const double d0 = 1.37, i0 = 0.029, s = 0.15;
    const pd_engine::Projection p = pd_engine::project(d0, i0, s, b);
    double d_prev = d0, i = i0;
    for (std::size_t t = 0; t < b.horizon(); ++t) {
        i = (1.0 - s) * i + s * b.market_rate[t];
        const double gamma = (1.0 + b.growth[t]) * (1.0 + b.inflation[t]) - 1.0;
        CHECK_CLOSE(p.effective_rate[t], i, 1e-15);
        CHECK_CLOSE(p.debt[t] - d_prev, p.snowball[t] - b.primary_balance[t] + b.sfa[t], 1e-14);
        CHECK_CLOSE(p.interest[t], d_prev * i / (1.0 + gamma), 1e-15);
        d_prev = p.debt[t];
    }
    // Refinancing share 0 keeps the effective rate; share 1 moves it to the market rate at once.
    const pd_engine::Projection frozen = pd_engine::project(d0, i0, 0.0, b);
    const pd_engine::Projection instant = pd_engine::project(d0, i0, 1.0, b);
    for (std::size_t t = 0; t < b.horizon(); ++t) {
        CHECK(frozen.effective_rate[t] == i0);
        CHECK(instant.effective_rate[t] == b.market_rate[t]);
    }
    CHECK(throws_invalid_argument([&] { pd_engine::project(d0, i0, 1.5, b); }));
    pd_engine::Baseline short_b = b;
    short_b.sfa.pop_back();
    CHECK(throws_invalid_argument([&] { pd_engine::project(d0, i0, 0.1, short_b); }));
}

void test_closed_forms() {
    const std::size_t H = 30;
    const double d0 = 1.35, g = 0.008, pi = 0.02, r = 0.036, s = 0.12, i0 = 0.028;
    const double gamma = (1.0 + g) * (1.0 + pi) - 1.0;
    // Effective rate with a constant market rate: i_t = r + (i0 - r)(1 - s)^t.
    const pd_engine::Projection p = pd_engine::project(d0, i0, s, constant_baseline(H, g, pi, r, 0.0));
    for (std::size_t t = 0; t < H; ++t)
        CHECK_CLOSE(p.effective_rate[t], r + (i0 - r) * std::pow(1.0 - s, static_cast<double>(t + 1)), 1e-15);
    // Without a primary balance and with i = r throughout, d_t = d0 ((1 + i)/(1 + gamma))^t.
    const pd_engine::Projection q = pd_engine::project(d0, r, s, constant_baseline(H, g, pi, r, 0.0));
    for (std::size_t t = 0; t < H; ++t)
        CHECK_CLOSE(q.debt[t], d0 * std::pow((1.0 + r) / (1.0 + gamma), static_cast<double>(t + 1)), 1e-12);
    // The debt-stabilising primary balance pb* = d0 (i - gamma) / (1 + gamma) keeps the ratio at d0.
    const double pb_star = d0 * (r - gamma) / (1.0 + gamma);
    const pd_engine::Projection stable = pd_engine::project(d0, r, s, constant_baseline(H, g, pi, r, pb_star));
    for (double d : stable.debt) CHECK_CLOSE(d, d0, 1e-13);
}

// ------------------------------------------------------------------------------------------------ stochastic DSA

void test_degenerate_shocks_reduce_to_projections() {
    const std::size_t H = 12;
    const pd_engine::Baseline b = constant_baseline(H, 0.01, 0.02, 0.035, 0.005, 0.001);
    const double d0 = 1.37, i0 = 0.03, s = 0.14;
    // No shocks at all: every path is the deterministic projection.
    const pd_engine::Fan none = pd_engine::stochastic_dsa(d0, i0, s, b, fixed_shock(0.0, 0.0, 0.0), 6, 1, 2);
    const pd_engine::Projection base = pd_engine::project(d0, i0, s, b);
    bool same = true;
    for (std::size_t p = 0; p < none.n_paths; ++p)
        for (std::size_t t = 0; t < H; ++t)
            same = same && std::abs(none.debt[p * H + t] - base.debt[t]) < 1e-14 &&
                   std::abs(none.interest[p * H + t] - base.interest[t]) < 1e-14;
    CHECK(same);
    // A constant shock e with A = 0 shifts the baseline by e and the primary balance by epsilon e_g.
    pd_engine::ShockModel m = fixed_shock(-0.01, 0.005, 0.01);
    m.epsilon = 0.5;
    pd_engine::Baseline shifted = constant_baseline(H, 0.0, 0.025, 0.045, 0.005 - 0.005, 0.001);
    const pd_engine::Fan fixed = pd_engine::stochastic_dsa(d0, i0, s, b, m, 3, 2, 1);
    const pd_engine::Projection manual = pd_engine::project(d0, i0, s, shifted);
    for (std::size_t t = 0; t < H; ++t) CHECK_CLOSE(fixed.debt[t], manual.debt[t], 1e-13);
    // VAR decay without residual shocks: u_t = A^t u_0 with A = 0.5 I.
    pd_engine::ShockModel decay = fixed_shock(0.0, 0.0, 0.0);
    decay.A = {0.5, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.5};
    decay.u0 = {0.02, -0.01, 0.004};
    pd_engine::Baseline decayed = b;
    for (std::size_t t = 0; t < H; ++t) {
        const double f = std::pow(0.5, static_cast<double>(t + 1));
        decayed.growth[t] += 0.02 * f;
        decayed.inflation[t] += -0.01 * f;
        decayed.market_rate[t] += 0.004 * f;
    }
    const pd_engine::Fan var_path = pd_engine::stochastic_dsa(d0, i0, s, b, decay, 2, 3, 1);
    const pd_engine::Projection var_manual = pd_engine::project(d0, i0, s, decayed);
    for (std::size_t t = 0; t < H; ++t) CHECK_CLOSE(var_path.debt[t], var_manual.debt[t], 1e-13);
    // A non-symmetric VAR: u_t[a] = sum_b A[a][b] u_{t-1}[b] (row-major, rows are the equations).
    pd_engine::ShockModel coupled = fixed_shock(0.0, 0.0, 0.0);
    coupled.A = {0.5, 0.2, 0.0, 0.0, 0.4, 0.1, 0.3, 0.0, 0.6};
    coupled.u0 = {0.02, -0.01, 0.004};
    pd_engine::Baseline propagated = b;
    double u[3] = {0.02, -0.01, 0.004};
    for (std::size_t t = 0; t < H; ++t) {
        double next[3];
        for (std::size_t a = 0; a < 3; ++a)
            next[a] = coupled.A[3 * a] * u[0] + coupled.A[3 * a + 1] * u[1] + coupled.A[3 * a + 2] * u[2];
        for (std::size_t a = 0; a < 3; ++a) u[a] = next[a];
        propagated.growth[t] += u[0];
        propagated.inflation[t] += u[1];
        propagated.market_rate[t] += u[2];
    }
    const pd_engine::Fan coupled_path = pd_engine::stochastic_dsa(d0, i0, s, b, coupled, 1, 3, 1);
    const pd_engine::Projection coupled_manual = pd_engine::project(d0, i0, s, propagated);
    for (std::size_t t = 0; t < H; ++t) CHECK_CLOSE(coupled_path.debt[t], coupled_manual.debt[t], 1e-13);
    // The market rate is floored at -2%.
    const pd_engine::Fan floored = pd_engine::stochastic_dsa(d0, i0, s, b, fixed_shock(0.0, 0.0, -0.2), 1, 4, 1);
    const pd_engine::Projection at_floor = pd_engine::project(d0, i0, s, constant_baseline(H, 0.01, 0.02, -0.02, 0.005, 0.001));
    for (std::size_t t = 0; t < H; ++t) CHECK_CLOSE(floored.debt[t], at_floor.debt[t], 1e-13);
    // Fiscal reaction rho (d_{t-1} - d0), written out.
    pd_engine::ShockModel react = fixed_shock(-0.02, 0.0, 0.0);
    react.rho = 0.1;
    const pd_engine::Fan reacting = pd_engine::stochastic_dsa(d0, i0, s, b, react, 1, 5, 1);
    double d = d0, i = i0;
    for (std::size_t t = 0; t < H; ++t) {
        const double g = b.growth[t] - 0.02;
        i = (1.0 - s) * i + s * b.market_rate[t];
        const double pb = b.primary_balance[t] + react.rho * (d - d0);
        d = pd_engine::step_debt(d, i, g, b.inflation[t], pb, b.sfa[t]);
        CHECK_CLOSE(reacting.debt[t], d, 1e-13);
    }
}

void test_bootstrap_and_threads() {
    const std::size_t H = 20;
    const pd_engine::Baseline b = constant_baseline(H, 0.01, 0.02, 0.035, 0.0);
    // Two residual rows, +e and -e for growth only, with A = 0: the growth deviation is +e or -e with probability
    // 1/2 each year, so the first-year debt takes two values with frequencies 1/2.
    pd_engine::ShockModel m = fixed_shock(0.0, 0.0, 0.0);
    m.residuals = {0.03, 0.0, 0.0, -0.03, 0.0, 0.0};
    const long long n = 100000;
    const pd_engine::Fan fan = pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, m, n, 17, 4);
    const double low = pd_engine::step_debt(1.3, 0.9 * 0.03 + 0.1 * 0.035, 0.04, 0.02, 0.0, 0.0);
    double share_low = 0.0;
    bool two_values = true;
    for (std::size_t p = 0; p < fan.n_paths; ++p) {
        const double d1 = fan.debt[p * H];
        const bool is_low = std::abs(d1 - low) < 1e-14;
        share_low += is_low ? 1.0 : 0.0;
        two_values = two_values && (is_low || std::abs(d1 - pd_engine::step_debt(1.3, 0.9 * 0.03 + 0.1 * 0.035, -0.02, 0.02, 0.0, 0.0)) < 1e-14);
    }
    CHECK(two_values);
    CHECK_CLOSE(share_low / static_cast<double>(n), 0.5, 4.0 * std::sqrt(0.25 / static_cast<double>(n)));
    // Primary-balance noise enters only through sigma_pb; each path has its own random stream.
    m.sigma_pb = 0.01;
    const pd_engine::Fan one = pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, m, 3000, 23, 1);
    const pd_engine::Fan many = pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, m, 3000, 23, 6);
    CHECK(one.debt == many.debt && one.interest == many.interest);
    CHECK(throws_invalid_argument([&] { pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, m, 0, 1); }));
    pd_engine::ShockModel bad = m;
    bad.A.pop_back();
    CHECK(throws_invalid_argument([&] { pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, bad, 10, 1); }));
    bad = m;
    bad.residuals.pop_back();
    CHECK(throws_invalid_argument([&] { pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, bad, 10, 1); }));
    bad = m;
    bad.u0 = {0.0, 0.0};
    CHECK(throws_invalid_argument([&] { pd_engine::stochastic_dsa(1.3, 0.03, 0.1, b, bad, 10, 1); }));
}

void test_adjustment_grid() {
    const std::size_t H = 10;
    const pd_engine::Baseline b = constant_baseline(H, 0.008, 0.02, 0.036, 0.008);
    pd_engine::ShockModel m = fixed_shock(0.0, 0.0, 0.0);
    m.A = {0.3, 0.0, 0.0, 0.1, 0.4, 0.0, 0.0, 0.1, 0.7};
    m.residuals = {0.02, 0.01, 0.005, -0.03, -0.005, 0.01, 0.01, -0.01, -0.008, -0.005, 0.004, 0.002};
    m.epsilon = 0.5;
    const std::vector<double> steps = {0.0, 0.0025, 0.005, 0.01};
    const std::vector<int> years = {1, 4, 7};
    const long long n = 4000;
    const std::vector<double> prob = pd_engine::adjustment_grid(1.37, 0.03, 0.12, b, m, steps, years, -1, 9, n, 31, 3);
    // Every cell reuses the same shocks, and the debt ratio falls path by path when the primary balance rises, so
    // the probability of a higher debt ratio can only fall with larger or longer adjustments.
    bool in_range = true, monotone = true;
    for (std::size_t a = 0; a < steps.size(); ++a)
        for (std::size_t y = 0; y < years.size(); ++y) {
            const double v = prob[a * years.size() + y];
            in_range = in_range && v >= 0.0 && v <= 1.0;
            if (a > 0) monotone = monotone && v <= prob[(a - 1) * years.size() + y];
            if (y > 0 && a > 0) monotone = monotone && v <= prob[a * years.size() + y - 1];
        }
    CHECK(in_range);
    CHECK(monotone);
    CHECK(prob[0] > prob[prob.size() - 1]);  // the adjustment matters in this set-up
    // A cell equals the share computed directly from the fan.
    pd_engine::Baseline adj = b;
    for (std::size_t t = 0; t < H; ++t) adj.primary_balance[t] += 0.005 * std::min(static_cast<int>(t) + 1, 4);
    const pd_engine::Fan fan = pd_engine::stochastic_dsa(1.37, 0.03, 0.12, adj, m, n, 31, 1);
    double higher = 0.0;
    for (std::size_t p = 0; p < fan.n_paths; ++p) higher += fan.debt[p * H + 9] > 1.37 ? 1.0 : 0.0;
    CHECK_CLOSE(prob[2 * years.size() + 1], higher / static_cast<double>(n), 1e-15);
    CHECK(throws_invalid_argument([&] { pd_engine::adjustment_grid(1.37, 0.03, 0.12, b, m, steps, years, 3, 3, 10, 1); }));
    CHECK(throws_invalid_argument([&] { pd_engine::adjustment_grid(1.37, 0.03, 0.12, b, m, steps, years, -1, 10, 10, 1); }));
}

}  // namespace

int main() {
    test_splitmix64_reference();
    test_xoshiro_streams();
    test_uniform_and_normal_moments();
    test_parallel_for();
    test_projection_identities();
    test_closed_forms();
    test_degenerate_shocks_reduce_to_projections();
    test_bootstrap_and_threads();
    test_adjustment_grid();
    std::printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
