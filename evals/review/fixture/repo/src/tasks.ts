export interface Task {
  id: string;
  state: "queued" | "running" | "done";
  feedback: string | null;
}

export interface TaskStore {
  insert(task: Task): Promise<void>;
  update(id: string, fields: Partial<Task>): Promise<void>;
  runnable(): Promise<Task[]>;
}

export async function createFixTask(store: TaskStore, id: string, feedback: string, emit: (t: Task) => void): Promise<Task> {
  const task: Task = { id, state: "running", feedback: null };
  await store.insert(task);
  await store.update(id, { feedback });
  emit({ ...task });
  return task;
}

export async function poll(store: TaskStore, run: (t: Task) => Promise<void>): Promise<void> {
  for (const task of await store.runnable()) {
    await run(task);
  }
}
