const CI = "https://ci.example.com/api";

export async function getBuild(id: string): Promise<unknown> {
  const res = await fetch(`${CI}/builds/${id}`);
  return res.json();
}
