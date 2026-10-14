package com.ian.frame;

import android.os.Handler;
import org.json.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Runs the real MainActivity poll/syncCookbook/cacheDeck/cacheImage/save methods on the host. */
public final class MainActivityCacheTest {
    private static final Map<String, byte[]> responses = new HashMap<>();
    private static final List<String> requests = Collections.synchronizedList(new ArrayList<>());
    private static Path root;
    private static MainActivity watched;
    private static long watchedBudget;
    private static boolean sawStagedBytes;
    private static int passed;
    private static int failed;
    private static final class HostActivity extends MainActivity {
        final File directory;
        volatile boolean pauseCommit;
        final CountDownLatch beforeCommit = new CountDownLatch(1), resumeCommit = new CountDownLatch(1);
        HostActivity(Path directory) { this.directory = directory.toFile(); }
        public File getFilesDir() {
            // Pause at the real save's first directory lookup, after all asset
            // downloads. No production hook or duplicate transaction algorithm.
            if (pauseCommit) for (StackTraceElement frame : Thread.currentThread().getStackTrace()) {
                if (frame.getClassName().equals(MainActivity.class.getName()) && frame.getMethodName().equals("save")) {
                    pauseCommit = false; beforeCommit.countDown();
                    try { check(resumeCommit.await(10, TimeUnit.SECONDS), "commit pause released"); }
                    catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                    break;
                }
            }
            return directory;
        }
    }
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    private static Field field(String name) throws Exception {
        Field field = MainActivity.class.getDeclaredField(name); field.setAccessible(true); return field;
    }
    private static Object call(MainActivity activity, String name, Class<?>[] types, Object... args) throws Exception {
        Method method = MainActivity.class.getDeclaredMethod(name, types); method.setAccessible(true);
        try { return method.invoke(activity, args); }
        catch (InvocationTargetException e) {
            Throwable cause = e.getCause(); if (cause instanceof Exception) throw (Exception) cause;
            throw (Error) cause;
        }
    }
    private static void sync(MainActivity a) throws Exception { call(a, "syncCookbook", new Class<?>[0]); }
    private static void cache(MainActivity a, String path, boolean cookbook, boolean thumb) throws Exception {
        call(a, "cacheImage", new Class<?>[]{String.class, boolean.class, boolean.class}, path, cookbook, thumb);
    }
    private static File image(MainActivity a, String path) throws Exception {
        return (File) call(a, "imageFile", new Class<?>[]{String.class}, path);
    }
    private static void save(MainActivity a, String name, JSONObject value) throws Exception {
        call(a, "save", new Class<?>[]{String.class, JSONObject.class}, name, value);
    }
    private static String hash(byte[] bytes) throws Exception {
        StringBuilder result = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(bytes)) result.append(String.format(Locale.US, "%02x", b & 255));
        return result.toString();
    }
    private static byte[] png(int w, int h, int size, int color) throws Exception {
        BufferedImage image = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) image.setRGB(x, y, color);
        ByteArrayOutputStream out = new ByteArrayOutputStream(); ImageIO.write(image, "png", out);
        check(size == 0 || out.size() <= size, "scaled PNG fixture fits");
        return size == 0 ? out.toByteArray() : Arrays.copyOf(out.toByteArray(), size);
    }
    private static String asset(byte[] bytes, boolean cookbook) throws Exception {
        String path = (cookbook ? "/cookbook/assets/" : "/media/") + hash(bytes) + ".png";
        responses.put(path, bytes); return path;
    }
    private static JSONObject recipe(int n, String thumb, String detail) {
        return new JSONObject().put("id", "r" + n).put("title", "Recipe " + n).put("category", "Beans")
            .put("photo_representative", true).put("thumbnail_path", thumb).put("detail_path", detail);
    }
    private static JSONObject cookbook(String revision, JSONArray recipes) {
        return new JSONObject().put("version", 1).put("revision", revision).put("recipes", recipes);
    }
    private static void respond(JSONObject value) throws Exception {
        responses.put("/cookbook", value.toString().getBytes("UTF-8"));
    }
    private static HostActivity activity() throws Exception {
        HostActivity a = new HostActivity(Files.createTempDirectory(root, "cache-"));
        field("base").set(a, "http://fixture"); return a;
    }
    private static void close(MainActivity a) throws Exception {
        ((ExecutorService) field("worker").get(a)).shutdownNow();
    }
    private static void unchangedCorruption(boolean sameLength) throws Exception {
        HostActivity a = activity();
        try {
            byte[] thumb = png(384, 200, 0, 0x638b56), detail = png(1280, 800, 0, 0x638b56);
            String tp = asset(thumb, true), dp = asset(detail, true);
            JSONObject value = cookbook(hash("unchanged".getBytes("UTF-8")), new JSONArray().put(recipe(0, tp, dp)));
            field("cookbook").set(a, value); respond(value); save(a, "cookbook.json", value);
            Files.write(image(a, tp).toPath(), thumb); Files.write(image(a, dp).toPath(), detail);
            byte[] before = Files.readAllBytes(new File(a.getFilesDir(), "cookbook.json").toPath());
            // Same-length change is in pixel data, so dimensions and byte count still look valid.
            byte[] bad = sameLength ? detail.clone() : Arrays.copyOf(detail, detail.length / 2);
            if (sameLength) bad[bad.length / 2] ^= 1;
            Files.write(image(a, dp).toPath(), bad);
            requests.clear(); sync(a);
            check(Arrays.equals(detail, Files.readAllBytes(image(a, dp).toPath())), "unchanged revision repairs " + (sameLength ? "same-length corruption" : "nonempty truncation"));
            check(Collections.frequency(requests, dp) == 1 && !requests.contains(tp), "only invalid asset redownloaded");
            check(Arrays.equals(before, Files.readAllBytes(new File(a.getFilesDir(), "cookbook.json").toPath())), "unchanged authoritative index preserved");
            requests.clear(); sync(a); check(requests.equals(Arrays.asList("/cookbook")), "valid fast path makes no image requests");
            // Corruption after an earlier successful verification must also be noticed.
            Files.write(image(a, dp).toPath(), bad); requests.clear(); sync(a);
            check(Arrays.equals(detail, Files.readAllBytes(image(a, dp).toPath())), "later file mutation invalidates verification");
        } finally { close(a); }
    }
    private static void dimensions() throws Exception {
        HostActivity a = activity();
        try {
            byte[] wrong = png(385, 200, 0, 0x638b56), detail = png(1280, 800, 0, 0x638b56);
            String tp = asset(wrong, true), dp = asset(detail, true);
            JSONObject value = cookbook(hash(wrong), new JSONArray().put(recipe(0, tp, dp)));
            field("cookbook").set(a, value); respond(value); save(a, "cookbook.json", value);
            Files.write(image(a, tp).toPath(), wrong); Files.write(image(a, dp).toPath(), detail);
            requests.clear(); boolean rejected = false;
            try { sync(a); } catch (IOException e) { rejected = true; }
            check(rejected && requests.contains(tp), "hash-valid wrong dimensions cannot use unchanged-revision fast path");
        } finally { close(a); }
    }
    @SuppressWarnings("unchecked")
    private static void decodeFailureInvalidation() throws Exception {
        HostActivity a = activity();
        try {
            byte[] thumb = png(384, 200, 0, 0x638b56), detail = png(1280, 800, 0, 0x638b56);
            String tp = asset(thumb, true), dp = asset(detail, true);
            JSONObject value = cookbook(hash(thumb), new JSONArray().put(recipe(0, tp, dp)));
            field("cookbook").set(a, value); respond(value); save(a, "cookbook.json", value);
            Files.write(image(a, tp).toPath(), thumb); Files.write(image(a, dp).toPath(), detail);
            // A decode failure can occur despite a valid hash/bounds, e.g. pixel decode failure.
            ((Set<String>) field("invalidCookbookImages").get(a)).add(dp);
            requests.clear(); sync(a);
            check(Collections.frequency(requests, dp) == 1 && !requests.contains(tp), "decode failure marker prevents valid-hash fast path");
            check(!((Set<String>) field("invalidCookbookImages").get(a)).contains(dp), "successful verified repair clears decode failure marker");
        } finally { close(a); }
    }
    private static void failedRepairPreservesFile() throws Exception {
        HostActivity a = activity();
        try {
            byte[] good = png(384, 200, 0, 0x638b56); String path = asset(good, true);
            byte[] bad = Arrays.copyOf(good, good.length / 2); Files.write(image(a, path).toPath(), bad);
            responses.remove(path); boolean rejected = false;
            try { cache(a, path, true, true); } catch (IOException e) { rejected = true; }
            check(rejected && Arrays.equals(bad, Files.readAllBytes(image(a, path).toPath())), "failed repair preserves existing file until atomic replacement");
            check(!new File(image(a, path) + ".tmp").exists(), "failed download removes partial staging file");
        } finally { close(a); }
    }
    private static void scaled(MainActivity a, long budget) throws Exception {
        field("cacheLimitBytes").setLong(a, budget);
        field("deckAssetLimit").setInt(a, 8 * 4096);
        field("cookbookAssetLimit").setInt(a, 1536 * 4);
    }
    private static JSONArray deck(MainActivity a, int generation, boolean cached) throws Exception {
        JSONArray cards = new JSONArray();
        for (int n = 0; n < 19; n++) {
            byte[] bytes = new byte[8 * 4096]; Arrays.fill(bytes, (byte) (generation * 20 + n));
            String path = asset(bytes, false);
            if (cached) Files.write(image(a, path).toPath(), bytes);
            cards.put(new JSONObject().put("id", "photo-" + n).put("type", "image").put("image_path", path));
        }
        return cards;
    }
    private static JSONObject collection(MainActivity a, int generation, boolean cached) throws Exception {
        JSONArray recipes = new JSONArray();
        for (int n = 0; n < 50; n++) {
            byte[] thumb = png(384, 200, 1536 * 4, 0x530000 + generation * 100 + n);
            byte[] detail = png(1280, 800, 1536 * 4, 0x530000 + generation * 100 + n);
            String tp = asset(thumb, true), dp = asset(detail, true);
            if (cached) { Files.write(image(a, tp).toPath(), thumb); Files.write(image(a, dp).toPath(), detail); }
            recipes.put(recipe(n, tp, dp));
        }
        return cookbook(hash(new byte[]{(byte) generation}), recipes);
    }
    private static Map<Path, byte[]> authoritative(MainActivity a) throws Exception {
        Map<Path, byte[]> files = new HashMap<>();
        for (File file : a.getFilesDir().listFiles()) files.put(file.toPath(), Files.readAllBytes(file.toPath()));
        return files;
    }
    private static void intact(Map<Path, byte[]> files) throws Exception {
        for (Map.Entry<Path, byte[]> e : files.entrySet()) check(Arrays.equals(e.getValue(), Files.readAllBytes(e.getKey())), "authoritative index/asset preserved: " + e.getKey());
    }
    private static long bytes(MainActivity a) {
        long total = 0; for (File file : a.getFilesDir().listFiles()) total += file.length(); return total;
    }
    private static void simultaneousReplacement() throws Exception {
        HostActivity a = activity(); long budget = 480 * 4096L;
        try {
            scaled(a, budget);
            JSONObject oldDeck = new JSONObject().put("revision", 1).put("cards", deck(a, 0, true));
            JSONObject oldBook = collection(a, 0, true);
            save(a, "state.json", oldDeck); save(a, "cookbook.json", oldBook); field("cookbook").set(a, oldBook);
            Map<Path, byte[]> original = authoritative(a);
            // Both replacement generations staged before deferred trim; no 604 MiB fixture.
            call(a, "cacheDeck", new Class<?>[]{JSONArray.class}, deck(a, 1, false));
            JSONObject nextBook = collection(a, 1, false); respond(nextBook);
            watched = a; watchedBudget = budget; sawStagedBytes = false;
            requests.clear(); boolean rejected = false;
            try { sync(a); } catch (IOException e) { rejected = true; }
            finally { watched = null; }
            check(sawStagedBytes, "live .tmp bytes observed during replacement streaming");
            check(rejected, "combined 604 MiB-equivalent replacement rejected at incremental 480 MiB limit");
            check(bytes(a) <= budget, "committed + staged files never exceed scaled budget");
            intact(original);
            for (File file : a.getFilesDir().listFiles()) check(!file.getName().endsWith(".tmp"), "no partial asset exposed after budget failure");
            // Retrying after orphan cleanup recovers without deleting authoritative files.
            call(a, "trimCache", new Class<?>[0]); intact(original);
            requests.clear(); sync(a);
            check(!requests.isEmpty() && bytes(a) <= budget, "retry can commit cookbook within budget");
        } finally { close(a); }
    }
    private static void interruptedBudget() throws Exception {
        HostActivity a = activity();
        try {
            byte[] good = png(384, 200, 0, 0x638b56); String path = asset(good, true);
            scaled(a, good.length + 100); field("cookbookAssetLimit").setInt(a, good.length);
            Path interrupted = a.getFilesDir().toPath().resolve("img-interrupted.tmp"); Files.write(interrupted, new byte[101]);
            requests.clear(); boolean rejected = false;
            try { cache(a, path, true, true); } catch (IOException e) { rejected = true; }
            check(rejected && requests.isEmpty() && !image(a, path).exists(), "interrupted .tmp bytes counted before network/download");
            check(Files.size(interrupted) == 101, "budget failure does not alter interrupted files");
            call(a, "trimCache", new Class<?>[0]); cache(a, path, true, true);
            check(Arrays.equals(good, Files.readAllBytes(image(a, path).toPath())), "cleanup frees budget for valid atomic download");
            byte[] existing = Files.readAllBytes(image(a, path).toPath());
            JSONObject index = new JSONObject().put("padding", String.join("", Collections.nCopies(101, "x")));
            rejected = false; try { save(a, "cookbook.json", index); } catch (IOException e) { rejected = true; }
            check(rejected && !new File(a.getFilesDir(), "cookbook.json").exists(), "index staging included in combined disk budget");
            check(Arrays.equals(existing, Files.readAllBytes(image(a, path).toPath())), "index budget failure preserves assets");
        } finally { close(a); }
    }
    private static void interruptedDownload() throws Exception {
        HostActivity a = activity();
        try {
            byte[] good = png(384, 200, 0, 0x638b56); String path = asset(good, true);
            responses.put(path, Arrays.copyOf(good, good.length / 2));
            boolean rejected = false; try { cache(a, path, true, true); } catch (IOException e) { rejected = true; }
            check(rejected && !image(a, path).exists() && !new File(image(a, path) + ".tmp").exists(), "truncated download never published");
        } finally { close(a); }
    }
    private static void racingWriters() throws Exception {
        HostActivity a = activity(), b = new HostActivity(a.getFilesDir().toPath()); field("base").set(b, "http://fixture");
        try {
            scaled(a, 200); scaled(b, 200);
            field("deckAssetLimit").setInt(a, 150); field("deckAssetLimit").setInt(b, 150);
            byte[] one = new byte[150], two = new byte[150]; two[0] = 1;
            String first = asset(one, false), second = asset(two, false);
            CountDownLatch start = new CountDownLatch(1);
            ExecutorService workers = Executors.newFixedThreadPool(2);
            try {
                List<Future<Boolean>> results = new ArrayList<>();
                results.add(workers.submit(() -> { start.await(); try { cache(a, first, false, false); return true; } catch (IOException e) { return false; } }));
                results.add(workers.submit(() -> { start.await(); try { cache(b, second, false, false); return true; } catch (IOException e) { return false; } }));
                requests.clear(); start.countDown(); int successes = 0;
                for (Future<Boolean> result : results) if (result.get(10, TimeUnit.SECONDS)) successes++;
                check(successes == 1 && requests.size() == 1 && bytes(a) == 150, "budget admission/write is race-free across cache writers");
            } finally { workers.shutdownNow(); }
        } finally { close(a); close(b); }
    }
    private static void collectionTrimRace(boolean book, boolean abort) throws Exception {
        HostActivity a = activity(), b = new HostActivity(a.getFilesDir().toPath());
        ExecutorService worker = (ExecutorService) field("worker").get(a);
        CompletableFuture<Void> trimmed = new CompletableFuture<>();
        CountDownLatch trimStarted = new CountDownLatch(1);
        Thread trimmer = new Thread(() -> {
            trimStarted.countDown();
            try { call(b, "trimCache", new Class<?>[0]); trimmed.complete(null); }
            catch (Throwable e) { trimmed.completeExceptionally(e); }
        }, "second-activity-trim");
        try {
            String oldPhoto = asset(new byte[]{1}, false), nextPhoto = asset(new byte[]{2}, false);
            Files.write(image(a, oldPhoto).toPath(), new byte[]{1});
            JSONObject oldDeck = new JSONObject().put("revision", 1).put("cards", new JSONArray().put(
                new JSONObject().put("id", "photo").put("type", "image").put("image_path", oldPhoto)));
            JSONObject nextDeck = new JSONObject().put("revision", 2).put("cards", new JSONArray().put(
                new JSONObject().put("id", "photo").put("type", "image").put("image_path", nextPhoto)));
            byte[] oldThumb = png(384, 200, 0, 0x638b56), oldDetail = png(1280, 800, 0, 0x638b56);
            String ot = asset(oldThumb, true), od = asset(oldDetail, true);
            Files.write(image(a, ot).toPath(), oldThumb); Files.write(image(a, od).toPath(), oldDetail);
            JSONObject oldBook = cookbook(hash(oldThumb), new JSONArray().put(recipe(0, ot, od)));
            String nt = asset(png(384, 200, 0, 0x123456), true), nd = asset(png(1280, 800, 0, 0x123456), true);
            JSONObject nextBook = cookbook(hash("replacement".getBytes("UTF-8")), new JSONArray().put(recipe(0, nt, nd)));
            save(a, "state.json", oldDeck); save(a, "cookbook.json", oldBook);
            field("cookbook").set(a, oldBook);
            Map<Path, byte[]> original = authoritative(a);
            String index = book ? "cookbook.json" : "state.json";
            byte[] oldIndex = Files.readAllBytes(a.directory.toPath().resolve(index));
            responses.put("/state", nextDeck.toString().getBytes("UTF-8"));
            respond(nextBook);
            // Keep this deck poll independent of cookbook's later polling interval.
            field("cookbookCheck").setLong(a, System.currentTimeMillis());
            a.pauseCommit = true;
            Future<?> synced;
            if (book) synced = worker.submit(() -> { sync(a); return null; });
            else { call(a, "poll", new Class<?>[0]); synced = worker.submit(() -> {}); }
            check(a.beforeCommit.await(10, TimeUnit.SECONDS), "production sync reached index publication");
            List<String> incoming = book ? Arrays.asList(nt, nd) : Arrays.asList(nextPhoto);
            for (String path : incoming) check(image(a, path).isFile(), "incoming asset downloaded before commit");
            check(Arrays.equals(oldIndex, Files.readAllBytes(a.directory.toPath().resolve(index))), "old index remains authoritative during download");
            trimmer.start(); check(trimStarted.await(10, TimeUnit.SECONDS), "second Activity started trim");
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while (!trimmed.isDone() && trimmer.getState() != Thread.State.BLOCKED && System.nanoTime() < deadline) Thread.sleep(1);
            check(!trimmed.isDone() && trimmer.getState() == Thread.State.BLOCKED,
                "second Activity trim must wait between asset download and index commit");
            if (abort) {
                // Invoke the real lifecycle method: shutdownNow interrupts the paused
                // old worker, whose transaction must release the lock without commit.
                call(a, "onDestroy", new Class<?>[0]);
                check(worker.awaitTermination(10, TimeUnit.SECONDS), "destroyed worker aborts transaction");
            } else {
                a.resumeCommit.countDown(); synced.get(10, TimeUnit.SECONDS);
            }
            trimmed.get(10, TimeUnit.SECONDS);
            if (abort) {
                intact(original);
                for (String path : incoming) check(!image(a, path).exists(), "aborted incoming orphan pruned");
            } else {
                JSONObject committed = (JSONObject) call(b, "load", new Class<?>[]{String.class}, index);
                check(committed.toString().equals((book ? nextBook : nextDeck).toString()), "incoming index published");
                for (String path : incoming) check(image(b, path).isFile(), "committed asset survives second Activity trim");
                check(book ? image(b, oldPhoto).isFile() : image(b, ot).isFile() && image(b, od).isFile(), "other authoritative collection retained");
            }
        } finally {
            a.resumeCommit.countDown(); close(a); close(b);
            check(worker.awaitTermination(10, TimeUnit.SECONDS), "first worker stopped");
            trimmer.join(10000); check(!trimmer.isAlive(), "second Activity trim stopped");
        }
    }
    private interface Test { void run() throws Exception; }
    private static void test(String name, Test test) {
        responses.clear(); requests.clear();
        try { test.run(); passed++; System.out.println("PASS " + name); }
        catch (Throwable e) { failed++; System.out.println("FAIL " + name + ": " + e); e.printStackTrace(System.out); }
    }
    public static void main(String[] args) throws Exception {
        root = Paths.get(args[0]); Files.createDirectories(root);
        // Replaces transport only: MainActivity's actual connection/read/download code executes.
        URL.setURLStreamHandlerFactory(protocol -> !protocol.equals("http") ? null : new URLStreamHandler() {
            protected URLConnection openConnection(URL url) {
                return new HttpURLConnection(url) {
                    public void disconnect() {} public boolean usingProxy() { return false; } public void connect() {}
                    public InputStream getInputStream() throws IOException {
                        String path = url.getPath(); requests.add(path);
                        byte[] bytes = responses.get(path); if (bytes == null) throw new IOException("Interrupted fixture download");
                        return new ByteArrayInputStream(bytes) {
                            public synchronized int read(byte[] buffer, int offset, int count) {
                                if (watched != null) {
                                    check(MainActivityCacheTest.bytes(watched) <= watchedBudget, "combined disk budget during streaming");
                                    for (File staged : watched.getFilesDir().listFiles())
                                        if (staged.getName().endsWith(".tmp") && staged.length() > 0) sawStagedBytes = true;
                                }
                                // Multiple writes make in-progress .tmp accounting observable.
                                return super.read(buffer, offset, Math.min(count, 1024));
                            }
                        };
                    }
                };
            }
        });
        try {
            test("unchanged revision nonempty truncation", () -> unchangedCorruption(false));
            test("unchanged revision same-length corruption", () -> unchangedCorruption(true));
            test("unchanged revision wrong dimensions", MainActivityCacheTest::dimensions);
            test("decode failure invalidates verified asset", MainActivityCacheTest::decodeFailureInvalidation);
            test("failed repair preserves old file", MainActivityCacheTest::failedRepairPreservesFile);
            test("simultaneous deck + cookbook scaled budget", MainActivityCacheTest::simultaneousReplacement);
            test("interrupted .tmp and index budget", MainActivityCacheTest::interruptedBudget);
            test("interrupted download atomicity", MainActivityCacheTest::interruptedDownload);
            test("concurrent budget admission", MainActivityCacheTest::racingWriters);
            test("deck download-to-commit excludes second Activity trim", () -> collectionTrimRace(false, false));
            test("cookbook download-to-commit excludes second Activity trim", () -> collectionTrimRace(true, false));
            test("destroyed deck transaction preserves authoritative collections", () -> collectionTrimRace(false, true));
            test("destroyed cookbook transaction preserves authoritative collections", () -> collectionTrimRace(true, true));
        } finally {
            try (java.util.stream.Stream<Path> paths = Files.walk(root)) {
                paths.sorted(Comparator.reverseOrder()).filter(p -> !p.equals(root)).forEach(p -> { try { Files.delete(p); } catch (IOException e) { throw new UncheckedIOException(e); } });
            }
        }
        System.out.println(passed + " passed, " + failed + " failed"); if (failed > 0) throw new AssertionError("Cache regressions failed");
    }
}
