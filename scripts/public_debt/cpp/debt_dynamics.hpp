// Public debt dynamics: deterministic projections and stochastic debt
// sustainability analysis (DSA).
//
// Debt ratio (debt / nominal GDP), all rates in decimals per year:
//     d_t = d_{t-1} (1 + i_t) / ((1 + g_t)(1 + pi_t)) - pb_t + sfa_t
// with i_t the effective (average) interest rate on the debt stock, g_t real
// GDP growth, pi_t GDP deflator inflation, pb_t the primary balance and
// sfa_t stock-flow adjustments, both as shares of GDP.
//
// Effective interest rate: each year a share s of the debt is refinanced at
// the market rate r_t, so i_t = (1 - s) i_{t-1} + s r_t (s is roughly one over
// the average residual maturity of the debt).
//
// Stochastic DSA (in the spirit of the European Commission's and IMF's
// fan charts): the macro variables x_t = (g_t, pi_t, r_t) equal a baseline
// plus deviations u_t that follow a VAR(1), u_t = A u_{t-1} + e_t, with e_t
// resampled from historical residual vectors (preserving their correlation).
// The primary balance reacts to growth surprises (automatic stabilisers,
// semi-elasticity epsilon) and, optionally, to the debt level (fiscal
// reaction rho):
//     pb_t = pb_base_t + epsilon (g_t - g_base_t) + rho (d_{t-1} - d_0) + sigma_pb z_t.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

#include "parallel.hpp"
#include "random.hpp"

namespace pd_engine {

struct Baseline {
    std::vector<double> growth, inflation, market_rate, primary_balance, sfa;  // length H
    std::size_t horizon() const { return growth.size(); }
    void validate() const {
        const std::size_t h = growth.size();
        if (h == 0 || inflation.size() != h || market_rate.size() != h || primary_balance.size() != h || sfa.size() != h)
            throw std::invalid_argument("baseline paths must be non-empty and of equal length");
    }
};

struct Projection {
    std::vector<double> debt;           // d_1..d_H
    std::vector<double> effective_rate; // i_1..i_H
    std::vector<double> interest;       // interest spending / GDP
    std::vector<double> snowball;       // d_{t-1} (i_t - gamma_t) / (1 + gamma_t)
};

inline double step_debt(double d_prev, double i, double g, double pi, double pb, double sfa) {
    return d_prev * (1.0 + i) / ((1.0 + g) * (1.0 + pi)) - pb + sfa;
}

inline Projection project(double d0, double i0, double refinancing_share, const Baseline& b) {
    b.validate();
    if (!(refinancing_share >= 0.0 && refinancing_share <= 1.0)) throw std::invalid_argument("refinancing share must lie in [0, 1]");
    Projection p;
    const std::size_t H = b.horizon();
    p.debt.resize(H);
    p.effective_rate.resize(H);
    p.interest.resize(H);
    p.snowball.resize(H);
    double d = d0, i = i0;
    for (std::size_t t = 0; t < H; ++t) {
        i = (1.0 - refinancing_share) * i + refinancing_share * b.market_rate[t];
        const double gamma = (1.0 + b.growth[t]) * (1.0 + b.inflation[t]) - 1.0;
        p.interest[t] = d * i / (1.0 + gamma);
        p.snowball[t] = d * (i - gamma) / (1.0 + gamma);
        d = step_debt(d, i, b.growth[t], b.inflation[t], b.primary_balance[t], b.sfa[t]);
        p.debt[t] = d;
        p.effective_rate[t] = i;
    }
    return p;
}

struct ShockModel {
    std::vector<double> A;          // 3 x 3 VAR(1) matrix for (g, pi, r) deviations, row-major
    std::vector<double> residuals;  // n x 3 historical residuals, row-major
    std::vector<double> u0;         // initial deviations (3), usually the last observed ones
    double epsilon = 0.0;           // primary-balance response to growth surprises
    double rho = 0.0;               // fiscal reaction to the debt ratio
    double sigma_pb = 0.0;          // idiosyncratic primary-balance noise
};

struct Fan {
    std::size_t n_paths = 0, horizon = 0;
    std::vector<double> debt;       // (path, year) row-major
    std::vector<double> interest;   // interest / GDP
};

inline Fan stochastic_dsa(double d0, double i0, double refinancing_share, const Baseline& b, const ShockModel& m,
                          long long n_paths, std::uint64_t seed, int n_threads = 0) {
    b.validate();
    if (m.A.size() != 9 || m.u0.size() != 3 || m.residuals.empty() || m.residuals.size() % 3 != 0)
        throw std::invalid_argument("A must be 3x3, u0 of length 3 and residuals an n x 3 matrix");
    if (n_paths < 1) throw std::invalid_argument("n_paths must be positive");
    const std::size_t H = b.horizon();
    const std::size_t n_res = m.residuals.size() / 3;
    Fan fan;
    fan.n_paths = static_cast<std::size_t>(n_paths);
    fan.horizon = H;
    fan.debt.assign(fan.n_paths * H, 0.0);
    fan.interest.assign(fan.n_paths * H, 0.0);
    parallel_for(fan.n_paths, n_threads, [&](std::size_t p) {
        Xoshiro256 rng(seed, p);
        double u[3] = {m.u0[0], m.u0[1], m.u0[2]};
        double d = d0, i = i0;
        for (std::size_t t = 0; t < H; ++t) {
            const std::size_t k = std::min(static_cast<std::size_t>(rng.uniform() * n_res), n_res - 1);
            const double* e = &m.residuals[3 * k];
            double next[3];
            for (int a = 0; a < 3; ++a)
                next[a] = m.A[3 * a] * u[0] + m.A[3 * a + 1] * u[1] + m.A[3 * a + 2] * u[2] + e[a];
            for (int a = 0; a < 3; ++a) u[a] = next[a];
            const double g = b.growth[t] + u[0];
            const double pi = b.inflation[t] + u[1];
            const double r = std::max(b.market_rate[t] + u[2], -0.02);  // floor against implausible negative yields
            i = (1.0 - refinancing_share) * i + refinancing_share * r;
            const double noise = m.sigma_pb > 0.0 ? m.sigma_pb * rng.normal() : 0.0;
            const double pb = b.primary_balance[t] + m.epsilon * u[0] + m.rho * (d - d0) + noise;
            const double gamma = (1.0 + g) * (1.0 + pi) - 1.0;
            fan.interest[p * H + t] = d * i / (1.0 + gamma);
            d = step_debt(d, i, g, pi, pb, b.sfa[t]);
            fan.debt[p * H + t] = d;
        }
    });
    return fan;
}

// Probability that the debt ratio in year `year_index` (0-based) is above
// its level in year `reference_index` (-1 = the starting value d0), for a
// grid of constant annual improvements of the primary balance over
// `adjustment_years` (kept afterwards). Used to size fiscal adjustments.
inline std::vector<double> adjustment_grid(double d0, double i0, double refinancing_share, const Baseline& b,
                                           const ShockModel& m, const std::vector<double>& annual_steps,
                                           const std::vector<int>& adjustment_years, int reference_index,
                                           int year_index, long long n_paths, std::uint64_t seed, int n_threads = 0) {
    const int H = static_cast<int>(b.horizon());
    if (year_index < 0 || year_index >= H || reference_index < -1 || reference_index >= year_index)
        throw std::invalid_argument("invalid year indices");
    std::vector<double> out(annual_steps.size() * adjustment_years.size());
    for (std::size_t a = 0; a < annual_steps.size(); ++a) {
        for (std::size_t y = 0; y < adjustment_years.size(); ++y) {
            Baseline adj = b;
            for (int t = 0; t < H; ++t)
                adj.primary_balance[t] += annual_steps[a] * std::min(t + 1, adjustment_years[y]);
            const Fan fan = stochastic_dsa(d0, i0, refinancing_share, adj, m, n_paths, seed, n_threads);
            std::size_t higher = 0;
            for (std::size_t p = 0; p < fan.n_paths; ++p) {
                const double ref = reference_index < 0 ? d0 : fan.debt[p * H + reference_index];
                higher += fan.debt[p * H + year_index] > ref ? 1 : 0;
            }
            out[a * adjustment_years.size() + y] = static_cast<double>(higher) / static_cast<double>(fan.n_paths);
        }
    }
    return out;
}

}  // namespace pd_engine
