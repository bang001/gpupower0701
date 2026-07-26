#!/usr/bin/env python3
"""Shared, fail-closed platform metadata for the Softmax EX2 experiment.

The experiment's baseline is the scalar FP32 ``__expf`` path.  ``ptx_f16``
and ``ptx_f16x2`` are *native* PTX EX2 paths, not generic half-precision
fallbacks.  This module therefore marks them unavailable below ``sm_75``
instead of silently substituting a different calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


EXP_IMPLEMENTATIONS = ("fp32", "ptx_f16", "ptx_f16x2")
CTA_GRIDS = (16, 32, 48, 64)
SOFTMAX_COLS = (128, 256, 512, 1024, 2048)


@dataclass(frozen=True)
class SoftmaxPlatformProfile:
    """Static contract; runtime identity remains a binary/preflight gate."""

    name: str
    cuda_arch: int
    compute_capability: str
    full_sm_counts: tuple[int, ...]
    default_binary: Path
    native_ex2_supported: bool
    requires_cuda12: bool = False
    requires_board_environment_gate: bool = False


PLATFORM_PROFILES: dict[str, SoftmaxPlatformProfile] = {
    "rtx3090": SoftmaxPlatformProfile(
        name="rtx3090",
        cuda_arch=86,
        compute_capability="8.6",
        full_sm_counts=(82,),
        default_binary=Path("build-softmax/a100_fp16_softmax_energy"),
        native_ex2_supported=True,
    ),
    "v100": SoftmaxPlatformProfile(
        name="v100",
        cuda_arch=70,
        compute_capability="7.0",
        full_sm_counts=(80,),
        default_binary=Path("build-v100/a100_fp16_softmax_energy"),
        native_ex2_supported=False,
        requires_cuda12=True,
    ),
    "a100": SoftmaxPlatformProfile(
        name="a100",
        cuda_arch=80,
        compute_capability="8.0",
        full_sm_counts=(108,),
        default_binary=Path("build-a100/a100_fp16_softmax_energy"),
        native_ex2_supported=True,
        requires_board_environment_gate=True,
    ),
    "h100": SoftmaxPlatformProfile(
        name="h100",
        cuda_arch=90,
        compute_capability="9.0",
        # H100 SXM and PCIe expose different complete-device SM counts.
        full_sm_counts=(114, 132),
        default_binary=Path("build-h100/a100_fp16_softmax_energy"),
        native_ex2_supported=True,
        requires_board_environment_gate=True,
    ),
}


def profile_names() -> tuple[str, ...]:
    return tuple(PLATFORM_PROFILES)


def profile_for(name: str) -> SoftmaxPlatformProfile:
    try:
        return PLATFORM_PROFILES[name]
    except KeyError as error:
        raise ValueError(
            f"unknown Softmax target profile {name!r}; choose one of "
            + ", ".join(profile_names())
        ) from error


def implementation_status(
    profile_name: str, exp_impl: str, *, cuda_major: int | None = None
) -> tuple[str, str]:
    """Return ``(status, reason)`` without invoking a CUDA binary.

    ``skipped`` is deliberate and successful planning output.  It must not be
    converted into an executable fallback row or included in a three-way
    platform comparison.
    """

    profile = profile_for(profile_name)
    if exp_impl not in EXP_IMPLEMENTATIONS:
        raise ValueError(f"unknown exponential implementation: {exp_impl}")
    if profile.requires_cuda12 and cuda_major is not None and cuda_major >= 13:
        return "skipped", "cuda_toolchain_lacks_sm70"
    if exp_impl != "fp32" and not profile.native_ex2_supported:
        return "skipped", "native_ex2_requires_sm75"
    return "runnable", ""


def runnable_implementations(
    profile_name: str, *, cuda_major: int | None = None
) -> tuple[str, ...]:
    return tuple(
        exp_impl
        for exp_impl in EXP_IMPLEMENTATIONS
        if implementation_status(profile_name, exp_impl, cuda_major=cuda_major)[0]
        == "runnable"
    )


def assert_contract() -> None:
    """Small dependency-free regression check used by CLI self-tests."""

    for profile_name in ("rtx3090", "a100", "h100"):
        assert runnable_implementations(profile_name) == EXP_IMPLEMENTATIONS
    assert runnable_implementations("v100", cuda_major=12) == ("fp32",)
    assert implementation_status("v100", "ptx_f16", cuda_major=12) == (
        "skipped",
        "native_ex2_requires_sm75",
    )
    assert implementation_status("v100", "ptx_f16x2", cuda_major=12) == (
        "skipped",
        "native_ex2_requires_sm75",
    )
    assert implementation_status("v100", "fp32", cuda_major=13) == (
        "skipped",
        "cuda_toolchain_lacks_sm70",
    )


if __name__ == "__main__":
    assert_contract()
    print("softmax_platform_profiles_self_test=pass")
