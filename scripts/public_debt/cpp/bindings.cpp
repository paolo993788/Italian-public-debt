// pybind11 bindings exposing the debt engine as public_debt._core.
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <vector>

#include "debt_dynamics.hpp"

namespace py = pybind11;
using DoubleArray = py::array_t<double, py::array::c_style | py::array::forcecast>;

namespace {

std::vector<double> to_vector(const DoubleArray& a) {
    const auto buf = a.request();
    const double* ptr = static_cast<const double*>(buf.ptr);
    return std::vector<double>(ptr, ptr + buf.size);
}

py::array_t<double> to_array(const std::vector<double>& v) {
    py::array_t<double> out(v.size());
    std::copy(v.begin(), v.end(), out.mutable_data());
    return out;
}

py::array_t<double> to_matrix(const std::vector<double>& v, std::size_t rows, std::size_t cols) {
    py::array_t<double> out(std::vector<py::ssize_t>{static_cast<py::ssize_t>(rows), static_cast<py::ssize_t>(cols)});
    std::copy(v.begin(), v.end(), out.mutable_data());
    return out;
}

pd_engine::Baseline make_baseline(const DoubleArray& g, const DoubleArray& pi, const DoubleArray& r, const DoubleArray& pb,
                                  const DoubleArray& sfa) {
    pd_engine::Baseline b{to_vector(g), to_vector(pi), to_vector(r), to_vector(pb), to_vector(sfa)};
    b.validate();
    return b;
}

pd_engine::ShockModel make_shocks(const DoubleArray& A, const DoubleArray& residuals, const DoubleArray& u0, double epsilon,
                                  double rho, double sigma_pb) {
    pd_engine::ShockModel m;
    m.A = to_vector(A);
    m.residuals = to_vector(residuals);
    m.u0 = to_vector(u0);
    m.epsilon = epsilon;
    m.rho = rho;
    m.sigma_pb = sigma_pb;
    return m;
}

}  // namespace

PYBIND11_MODULE(_core, m) {
    m.doc() = "C++ public debt dynamics and stochastic debt sustainability engine for public_debt.";

    m.def(
        "project",
        [](double d0, double i0, double refinancing_share, const DoubleArray& growth, const DoubleArray& inflation,
           const DoubleArray& market_rate, const DoubleArray& primary_balance, const DoubleArray& sfa) {
            const auto p = pd_engine::project(d0, i0, refinancing_share,
                                              make_baseline(growth, inflation, market_rate, primary_balance, sfa));
            py::dict d;
            d["debt"] = to_array(p.debt);
            d["effective_rate"] = to_array(p.effective_rate);
            d["interest"] = to_array(p.interest);
            d["snowball"] = to_array(p.snowball);
            return d;
        },
        py::arg("d0"), py::arg("i0"), py::arg("refinancing_share"), py::arg("growth"), py::arg("inflation"),
        py::arg("market_rate"), py::arg("primary_balance"), py::arg("sfa"),
        "Deterministic projection of the debt ratio with a gradually repricing effective interest rate.");

    m.def(
        "stochastic_dsa",
        [](double d0, double i0, double refinancing_share, const DoubleArray& growth, const DoubleArray& inflation,
           const DoubleArray& market_rate, const DoubleArray& primary_balance, const DoubleArray& sfa, const DoubleArray& A,
           const DoubleArray& residuals, const DoubleArray& u0, double epsilon, double rho, double sigma_pb,
           long long n_paths, std::uint64_t seed, int n_threads) {
            const auto b = make_baseline(growth, inflation, market_rate, primary_balance, sfa);
            const auto s = make_shocks(A, residuals, u0, epsilon, rho, sigma_pb);
            pd_engine::Fan fan;
            {
                py::gil_scoped_release release;
                fan = pd_engine::stochastic_dsa(d0, i0, refinancing_share, b, s, n_paths, seed, n_threads);
            }
            py::dict d;
            d["debt"] = to_matrix(fan.debt, fan.n_paths, fan.horizon);
            d["interest"] = to_matrix(fan.interest, fan.n_paths, fan.horizon);
            return d;
        },
        py::arg("d0"), py::arg("i0"), py::arg("refinancing_share"), py::arg("growth"), py::arg("inflation"),
        py::arg("market_rate"), py::arg("primary_balance"), py::arg("sfa"), py::arg("A"), py::arg("residuals"),
        py::arg("u0"), py::arg("epsilon") = 0.0, py::arg("rho") = 0.0, py::arg("sigma_pb") = 0.0,
        py::arg("n_paths") = 100000, py::arg("seed") = 12345, py::arg("n_threads") = 0,
        "Monte Carlo fan chart of the debt ratio with bootstrapped VAR(1) macro shocks.");

    m.def(
        "adjustment_grid",
        [](double d0, double i0, double refinancing_share, const DoubleArray& growth, const DoubleArray& inflation,
           const DoubleArray& market_rate, const DoubleArray& primary_balance, const DoubleArray& sfa, const DoubleArray& A,
           const DoubleArray& residuals, const DoubleArray& u0, double epsilon, double rho, double sigma_pb,
           const DoubleArray& annual_steps, const std::vector<int>& adjustment_years, int reference_index, int year_index,
           long long n_paths, std::uint64_t seed, int n_threads) {
            const auto b = make_baseline(growth, inflation, market_rate, primary_balance, sfa);
            const auto s = make_shocks(A, residuals, u0, epsilon, rho, sigma_pb);
            const auto steps = to_vector(annual_steps);
            std::vector<double> out;
            {
                py::gil_scoped_release release;
                out = pd_engine::adjustment_grid(d0, i0, refinancing_share, b, s, steps, adjustment_years, reference_index,
                                                 year_index, n_paths, seed, n_threads);
            }
            return to_matrix(out, steps.size(), adjustment_years.size());
        },
        py::arg("d0"), py::arg("i0"), py::arg("refinancing_share"), py::arg("growth"), py::arg("inflation"),
        py::arg("market_rate"), py::arg("primary_balance"), py::arg("sfa"), py::arg("A"), py::arg("residuals"),
        py::arg("u0"), py::arg("epsilon"), py::arg("rho"), py::arg("sigma_pb"), py::arg("annual_steps"),
        py::arg("adjustment_years"), py::arg("reference_index"), py::arg("year_index"), py::arg("n_paths") = 20000,
        py::arg("seed") = 12345, py::arg("n_threads") = 0,
        "Probability that debt is higher at year_index than at reference_index, for a grid of fiscal adjustments.");
}
