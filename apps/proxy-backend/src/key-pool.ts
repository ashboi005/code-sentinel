export interface SelectedKey {
  index: number;
  value: string;
}

export class KeyPool {
  private readonly keys: string[];
  private cursor = 0;

  constructor(keys: string[]) {
    const normalized = keys.map((key) => key.trim()).filter(Boolean);
    if (normalized.length === 0) {
      throw new Error("KeyPool requires at least one key");
    }

    this.keys = normalized;
  }

  select(): SelectedKey {
    const index = this.cursor;
    this.cursor = (this.cursor + 1) % this.keys.length;
    return { index, value: this.keys[index] };
  }

  size(): number {
    return this.keys.length;
  }

  availableCount(): number {
    return this.keys.length;
  }
}
