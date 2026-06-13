import { describe, expect, test } from "bun:test";
import { KeyPool } from "../src/key-pool";

describe("KeyPool", () => {
  test("rotates keys round-robin", () => {
    const pool = new KeyPool(["one", "two"], 1_000);

    expect(pool.select(0)?.value).toBe("one");
    expect(pool.select(0)?.value).toBe("two");
    expect(pool.select(0)?.value).toBe("one");
  });

  test("skips keys that are cooling down", () => {
    const pool = new KeyPool(["one", "two"], 1_000);

    const selected = pool.select(100);
    expect(selected?.value).toBe("one");

    pool.markRateLimited(selected!.index, 100);

    expect(pool.select(200)?.value).toBe("two");
    expect(pool.select(200)?.value).toBe("two");
    expect(pool.select(1_101)?.value).toBe("one");
  });
});
