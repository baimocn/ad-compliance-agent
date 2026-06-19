"""
性能基准测试工具 — 并发审查吞吐量与延迟测试

测试模式：
1. mock 模式：使用本地 Mock Agent，模拟 LLM 调用延迟，测试并发框架本身的开销
2. live 模式：连接真实 FastAPI 服务，测试端到端性能

用法：
    # Mock 模式（无需启动服务）
    python3 benchmark_perf.py --mode mock --concurrency 10 50 100

    # Live 模式（需先启动 FastAPI 服务）
    python3 benchmark_perf.py --mode live --url http://localhost:8000 --concurrency 10 50 100
"""
import sys
import time
import json
import asyncio
import argparse
import statistics
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'pipeline'))
sys.path.insert(0, str(_PROJECT / 'backend'))

# ---- 测试文案 ----
TEST_TEXTS = [
    "全网最低价，买到就是赚到！限时特惠手慢无！品质有保障放心选购。",
    "这款手机搭载目前最高频率的骁龙8 Gen3处理器（3.4GHz），最大支持128GB内存扩展。",
    "使用三天包瘦十斤，无效全额退款，不瘦不要钱！治愈率高达99%。",
    "本品含维生素C和烟酰胺，有助于维持皮肤健康状态。",
    "比XX品牌省电50%，质量远超同行，吊打一切竞品，遥遥领先！",
    "本理财产品年化收益15%以上，保本保息零风险，稳赚不赔。",
    "考研保过班不过全额退款，命题组老师亲自授课，押题命中率90%。",
    "纯天然有机食品，零添加更健康，妈妈的安心之选。",
    "我个人觉得这家店的咖啡是我喝过最好喝的，推荐大家试试。",
    "上市三个月突破百万销量，行业遥遥领先，销量第一，爆款热销。",
]


# ============================================================
# Mock Agent 基准测试
# ============================================================

class MockFastAgent:
    """Mock 审查 Agent，模拟固定延迟。

    模拟真实场景：
    - 禁用词匹配：~10ms（确定性，快）
    - 语境判断：~200ms (LLM调用，可并发)
    - RAG 检索：~50ms
    - 建议生成：~100ms
    """

    def __init__(
        self,
        llm_latency_ms: float = 200.0,
        review_concurrency: int = 5,
        llm_concurrency: int = 3,
    ):
        self._llm_latency = llm_latency_ms / 1000.0
        self._judge_sem = asyncio.Semaphore(llm_concurrency)
        self._review_sem = asyncio.Semaphore(review_concurrency)

    async def review(self, text: str, industry: str = "general") -> dict:
        """模拟一次完整审查。"""
        async with self._review_sem:
            # 步骤1: 禁用词匹配 ~10ms
            await asyncio.sleep(0.01)
            hit_count = max(1, len(text) // 50)  # 模拟命中数

            # 步骤2: 语境判断 ~200ms per hit (并发)
            start = time.time()
            judge_tasks = [self._mock_judge(text) for _ in range(hit_count)]
            await asyncio.gather(*judge_tasks)
            judge_time = time.time() - start

            # 步骤3: RAG 检索 ~50ms
            await asyncio.sleep(0.05)

            # 步骤4: 建议生成 ~100ms
            await asyncio.sleep(0.1)

            total = time.time() - start + 0.01  # 加上步骤1的时间
            return {
                "hit_count": hit_count,
                "judge_time_ms": round(judge_time * 1000, 1),
                "total_ms": round(total * 1000, 1),
            }

    async def _mock_judge(self, text: str) -> dict:
        """模拟一次 LLM 语境判断。"""
        async with self._judge_sem:
            await asyncio.sleep(self._llm_latency)
            return {"is_violation": True, "confidence": 0.85}


async def _run_mock_benchmark(
    concurrency: int,
    duration_s: int = 5,
    llm_latency_ms: float = 200.0,
    review_concurrency: int = 5,
    llm_concurrency: int = 3,
) -> dict:
    """运行 Mock 模式基准测试。

    Args:
        concurrency: 并发请求数
        duration_s: 测试时长（秒）
        llm_latency_ms: LLM 模拟延迟（毫秒）
        review_concurrency: 审查最大并发数
        llm_concurrency: LLM 最大并发数
    """
    agent = MockFastAgent(
        llm_latency_ms=llm_latency_ms,
        review_concurrency=review_concurrency,
        llm_concurrency=llm_concurrency,
    )
    latencies = []
    errors = 0
    total_requests = 0
    start_time = time.time()
    text_idx = 0

    async def worker():
        nonlocal total_requests, errors, text_idx
        while time.time() - start_time < duration_s:
            text = TEST_TEXTS[text_idx % len(TEST_TEXTS)]
            text_idx += 1
            req_start = time.time()
            try:
                await agent.review(text)
                latencies.append((time.time() - req_start) * 1000)
                total_requests += 1
            except Exception:
                errors += 1

    # 启动并发 worker
    tasks = [worker() for _ in range(concurrency)]
    await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    rps = total_requests / total_time if total_time > 0 else 0

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.5)] if n > 0 else 0
    p95 = latencies[int(n * 0.95)] if n > 0 else 0
    p99 = latencies[int(n * 0.99)] if n > 0 else 0
    avg = statistics.mean(latencies) if latencies else 0

    return {
        "concurrency": concurrency,
        "duration_s": round(total_time, 2),
        "total_requests": total_requests,
        "errors": errors,
        "error_rate": round(errors / max(total_requests + errors, 1), 4),
        "req_per_second": round(rps, 2),
        "avg_latency_ms": round(avg, 2),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "min_latency_ms": round(latencies[0], 2) if latencies else 0,
        "max_latency_ms": round(latencies[-1], 2) if latencies else 0,
    }


# ============================================================
# Live HTTP 基准测试
# ============================================================

async def _run_live_benchmark(url: str, concurrency: int, duration_s: int = 5) -> dict:
    """运行 Live HTTP 模式基准测试。"""
    try:
        import aiohttp
    except ImportError:
        return {"error": "需要安装 aiohttp: pip install aiohttp", "concurrency": concurrency}

    latencies = []
    errors = 0
    total_requests = 0
    start_time = time.time()
    text_idx = 0

    async def worker(session):
        nonlocal total_requests, errors, text_idx
        while time.time() - start_time < duration_s:
            text = TEST_TEXTS[text_idx % len(TEST_TEXTS)]
            text_idx += 1
            req_start = time.time()
            try:
                async with session.post(
                    f"{url}/api/review/async",
                    json={"text": text, "industry": "general"},
                ) as resp:
                    await resp.json()
                latencies.append((time.time() - req_start) * 1000)
                total_requests += 1
            except Exception:
                errors += 1

    async with aiohttp.ClientSession() as session:
        tasks = [worker(session) for _ in range(concurrency)]
        await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    rps = total_requests / total_time if total_time > 0 else 0

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.5)] if n > 0 else 0
    p95 = latencies[int(n * 0.95)] if n > 0 else 0
    p99 = latencies[int(n * 0.99)] if n > 0 else 0
    avg = statistics.mean(latencies) if latencies else 0

    return {
        "concurrency": concurrency,
        "duration_s": round(total_time, 2),
        "total_requests": total_requests,
        "errors": errors,
        "error_rate": round(errors / max(total_requests + errors, 1), 4),
        "req_per_second": round(rps, 2),
        "avg_latency_ms": round(avg, 2),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
        "min_latency_ms": round(latencies[0], 2) if latencies else 0,
        "max_latency_ms": round(latencies[-1], 2) if latencies else 0,
    }


# ============================================================
# 报告生成
# ============================================================

def _generate_report(results: list[dict], mode: str) -> dict:
    """生成基准测试报告。"""
    return {
        "mode": mode,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_texts_count": len(TEST_TEXTS),
        "results": results,
        "summary": {
            "best_rps": max(r.get("req_per_second", 0) for r in results) if results else 0,
            "max_p99": max(r.get("p99_latency_ms", 0) for r in results) if results else 0,
            "target_rps_5": all(r.get("req_per_second", 0) >= 5 for r in results) if results else False,
            "target_p99_2s": all(r.get("p99_latency_ms", 0) <= 2000 for r in results) if results else False,
        },
    }


def _print_results(results: list[dict]):
    """打印基准测试结果表格。"""
    print(f"\n{'并发数':<10} {'RPS':>8} {'平均(ms)':>10} {'P50(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'错误率':>8}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"{r['concurrency']:<10} {'ERROR':>8}")
            continue
        print(f"{r['concurrency']:<10} {r['req_per_second']:>8.2f} {r['avg_latency_ms']:>10.2f} "
              f"{r['p50_latency_ms']:>10.2f} {r['p95_latency_ms']:>10.2f} {r['p99_latency_ms']:>10.2f} "
              f"{r['error_rate']:>7.1%}")
    print()


async def main():
    parser = argparse.ArgumentParser(description="广告法合规审查 Agent 性能基准测试")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock", help="测试模式")
    parser.add_argument("--url", default="http://localhost:8000", help="Live 模式下的服务地址")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[10, 50, 100],
                        help="并发数列表，默认 10 50 100")
    parser.add_argument("--duration", type=int, default=5, help="每个并发级别的测试时长(秒)")
    parser.add_argument("--llm-latency", type=float, default=200, help="LLM 模拟延迟(ms)，默认 200")
    parser.add_argument("--review-concurrency", type=int, default=5, help="审查最大并发数，默认 5")
    parser.add_argument("--llm-concurrency", type=int, default=3, help="LLM 最大并发数，默认 3")
    parser.add_argument("--output", default=None, help="报告输出 JSON 文件路径")
    args = parser.parse_args()

    print("=" * 70)
    print("广告法合规审查 Agent — 性能基准测试")
    print(f"模式: {args.mode}")
    print(f"并发级别: {args.concurrency}")
    print(f"测试时长/级别: {args.duration}s")
    if args.mode == "mock":
        print(f"LLM 延迟: {args.llm_latency}ms")
        print(f"审查并发上限: {args.review_concurrency}")
        print(f"LLM 并发上限: {args.llm_concurrency}")
    print("=" * 70)

    results = []
    for c in args.concurrency:
        print(f"\n▶ 测试并发 {c} ...")
        if args.mode == "mock":
            r = await _run_mock_benchmark(
                c, duration_s=args.duration,
                llm_latency_ms=args.llm_latency,
                review_concurrency=args.review_concurrency,
                llm_concurrency=args.llm_concurrency,
            )
        else:
            r = await _run_live_benchmark(args.url, c, duration_s=args.duration)
        results.append(r)

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    _print_results(results)

    # 目标检查
    report = _generate_report(results, args.mode)
    s = report["summary"]
    print("目标检查:")
    print(f"  吞吐量 ≥ 5 req/s: {'✓ PASS' if s['target_rps_5'] else '✗ FAIL'} (最佳 {s['best_rps']:.2f})")
    print(f"  P99 延迟 < 2s:    {'✓ PASS' if s['target_p99_2s'] else '✗ FAIL'} (最高 {s['max_p99']:.0f}ms)")
    print()

    # 保存报告
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {args.output}")
    else:
        out_path = str(Path(__file__).parent / f"benchmark_report_{args.mode}_{int(time.time())}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {out_path}")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
