package android.os;
import java.util.*;
/** Queue UI callbacks, matching the worker/UI separation without launching Android. */
public class Handler {
    private final Queue<Runnable> queue = new ArrayDeque<>();
    public boolean post(Runnable runnable) { queue.add(runnable); return true; }
    public boolean postDelayed(Runnable runnable, long delay) { return true; }
    public void removeCallbacksAndMessages(Object token) { queue.clear(); }
    public void drain() { while (!queue.isEmpty()) queue.remove().run(); }
}
