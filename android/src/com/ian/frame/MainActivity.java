package com.ian.frame;

import android.app.*;
import android.os.*;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.text.*;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends Activity {
    private static final String URL = BuildConfig.FRAME_URL, TOKEN = BuildConfig.READ_TOKEN;
    private final Handler handler = new Handler();
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final LibraryNavigation library = new LibraryNavigation();
    private final ArrayList<ImageView> imageViews = new ArrayList<>();
    private final ArrayList<Bitmap> bitmaps = new ArrayList<>();
    private JSONObject state;
    private volatile JSONObject cookbook;
    private JSONArray cards, recipes;
    private int index = 0;
    private long revision = -1, cookbookCheck = 0;
    // Private limits allow scaled host regressions; production always uses these defaults.
    private long cacheLimitBytes = OfflineAssets.MAX_CACHE_BYTES;
    private int deckAssetLimit = 8 * 1024 * 1024, cookbookAssetLimit = OfflineAssets.MAX_COOKBOOK_ASSET;
    private final Set<String> invalidCookbookImages = Collections.newSetFromMap(new ConcurrentHashMap<String, Boolean>());
    private volatile boolean destroyed = false;
    private boolean busy = false, connected = false;
    private String tab = "Photos", base, photoId = "clock", weekId = "dinner-week";
    private float downX, downY;
    private LinearLayout screen, body;
    private TextView status, clock, date;
    private WebView web;
    private int color = Color.parseColor("#BBD7B2");
    private final int background = Color.parseColor("#161B19"), white = Color.parseColor("#F1F0E7"), muted = Color.parseColor("#A8B5AC");

    private final Runnable timer = new Runnable() { public void run() {
        if (destroyed) return;
        if (clock != null) clock.setText(new SimpleDateFormat("h:mm", Locale.US).format(new Date()));
        if (date != null) date.setText(new SimpleDateFormat("EEEE, MMMM d", Locale.US).format(new Date()));
        handler.postDelayed(this, 1000);
    }};
    private final Runnable poller = new Runnable() { public void run() {
        if (destroyed) return;
        poll(); handler.postDelayed(this, 3000);
    }};

    public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        base = getPreferences(0).getString("server", URL);
        try {
            state = load("state.json");
            if (state.getJSONArray("cards").length() < 1 || state.getJSONArray("cards").length() > 20) throw new IOException("Invalid deck");
        } catch (Exception e) { state = defaults(); }
        revision = state.optLong("revision", 0);
        photoId = getPreferences(0).getString("photo_id", preferredPhoto());
        weekId = getPreferences(0).getString("week_id", "dinner-week");
        try { cookbook = load("cookbook.json"); validateCookbook(cookbook); }
        catch (Exception e) { cookbook = new JSONObject(); }
        recipes = cookbook.optJSONArray("recipes");
        if (recipes == null) recipes = new JSONArray();
        render(); handler.post(timer); handler.post(poller);
    }
    private JSONObject load(String name) throws Exception {
        return new JSONObject(read(new FileInputStream(new File(getFilesDir(), name))));
    }
    private JSONObject defaults() {
        try { return new JSONObject("{\"revision\":0,\"cards\":[{\"id\":\"clock\",\"type\":\"clock\",\"accent\":\"#BBD7B2\"},{\"id\":\"hermes\",\"type\":\"text\",\"eyebrow\":\"HERMES\",\"title\":\"Room for a new thought.\",\"body\":\"Your agent can send notes, images, and updates here. Swipe to explore.\",\"accent\":\"#D6C3A5\"}]}"); }
        catch (Exception e) { return new JSONObject(); }
    }
    private String preferredPhoto() {
        String focus = state.optString("focus_id");
        JSONArray all = state.optJSONArray("cards");
        if (!focus.isEmpty() && !LibraryNavigation.weekly(focus)) return focus;
        for (int i = 0; all != null && i < all.length(); i++) {
            JSONObject c = all.optJSONObject(i);
            if (c != null && "image".equals(c.optString("type")) && !LibraryNavigation.weekly(c.optString("id"))) return c.optString("id");
        }
        return "clock";
    }
    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private TextView text(String s, int size, int c) {
        TextView t = new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(c);
        t.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL)); return t;
    }
    private TextView action(String label, Runnable run) {
        TextView t = text(label, 19, white); t.setGravity(Gravity.CENTER);
        t.setPadding(dp(14), dp(5), dp(14), dp(5)); t.setOnClickListener(v -> run.run()); return t;
    }
    private GradientDrawable rounded(int c, float radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(c); d.setCornerRadius(dp(radius)); return d;
    }
    private void releaseImages() {
        for (ImageView view : imageViews) view.setImageDrawable(null);
        imageViews.clear();
        // Drop references; Android's render thread may still hold the detached
        // screen for this frame. Explicit recycle can race its display list.
        bitmaps.clear();
    }
    private void rememberCard() {
        if (cards == null || tab.equals("Cookbook")) return;
        JSONObject c = cards.optJSONObject(index);
        if (c != null) {
            if (tab.equals("This Week")) weekId = c.optString("id"); else photoId = c.optString("id");
            getPreferences(0).edit().putString("photo_id", photoId).putString("week_id", weekId).apply();
        }
    }
    private void switchTab(String next) { rememberCard(); tab = next; render(); }
    private void selectDeck() {
        cards = new JSONArray();
        JSONArray all = state.optJSONArray("cards");
        String wanted = tab.equals("This Week") ? weekId : photoId;
        index = 0;
        for (int i = 0; all != null && i < all.length(); i++) {
            JSONObject c = all.optJSONObject(i);
            if (c != null && LibraryNavigation.weekly(c.optString("id")) == tab.equals("This Week")) {
                if (c.optString("id").equals(wanted)) index = cards.length();
                cards.put(c);
            }
        }
    }
    private void render() {
        if (destroyed) return;
        if (web != null) { web.destroy(); web = null; }
        clock = null; date = null;
        LinearLayout previous = screen;
        screen = new LinearLayout(this); screen.setOrientation(1); screen.setBackgroundColor(background);
        screen.setPadding(dp(16), dp(8), dp(16), dp(8)); setContentView(screen);
        if (previous != null) previous.removeAllViews();
        releaseImages();
        LinearLayout top = new LinearLayout(this); top.setGravity(Gravity.CENTER_VERTICAL);
        TextView brand = text("F R A M E", 14, muted);
        brand.setPadding(dp(10), 0, dp(22), 0);
        brand.setOnLongClickListener(v -> { settings(); return true; }); top.addView(brand);
        for (String name : new String[]{"Photos", "This Week", "Cookbook"}) {
            TextView item = action(name, () -> switchTab(name));
            item.setBackground(rounded(tab.equals(name) ? Color.parseColor("#3A443F") : background, 6));
            top.addView(item, new LinearLayout.LayoutParams(dp(135), dp(44)));
        }
        status = text(connected ? "● CONNECTED" : "OFFLINE · SAVED CONTENT", 12, muted);
        status.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        top.addView(status, new LinearLayout.LayoutParams(0, dp(44), 1)); screen.addView(top);
        body = new LinearLayout(this); body.setOrientation(1); body.setGravity(Gravity.CENTER_VERTICAL);
        screen.addView(body, new LinearLayout.LayoutParams(-1, 0, 1));
        if (tab.equals("Cookbook")) { renderLibrary(); return; }
        selectDeck();
        if (cards.length() == 0) {
            body.addView(text("No accepted weekly menu is saved yet.", 28, white));
            body.addView(text("Recipes appear here after the specific weekly menu is accepted.", 21, muted)); return;
        }
        JSONObject card = cards.optJSONObject(index);
        try { color = Color.parseColor(card.optString("accent", "#BBD7B2")); }
        catch (Exception e) { color = Color.parseColor("#BBD7B2"); }
        renderCard(card);
        LinearLayout footer = new LinearLayout(this); footer.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout dots = new LinearLayout(this);
        for (int i = 0; i < cards.length(); i++) {
            final int n = i;
            View dot = new View(this); dot.setBackground(rounded(i == index ? color : Color.parseColor("#3A443F"), 8));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(i == index ? 28 : 8), dp(8)); lp.rightMargin = dp(12);
            dots.addView(dot, lp); dot.setOnClickListener(v -> { index = n; rememberCard(); render(); });
        }
        footer.addView(dots, new LinearLayout.LayoutParams(0, dp(32), 1));
        footer.addView(action("‹", () -> swipe(-1)));
        footer.addView(text(String.format(Locale.US, "%02d / %02d", index + 1, cards.length()), 14, muted));
        footer.addView(action("›", () -> swipe(1))); screen.addView(footer);
    }
    private void renderCard(JSONObject card) {
        String type = card.optString("type", "text");
        if (type.equals("clock")) {
            body.setPadding(dp(40), 0, dp(40), 0);
            body.addView(text("MAKE ROOM FOR TODAY", 14, color)); clock = text("", 148, white);
            clock.setTypeface(Typeface.create("sans-serif-light", 0)); clock.setIncludeFontPadding(false); body.addView(clock);
            date = text("", 30, muted); body.addView(date);
            clock.setText(new SimpleDateFormat("h:mm", Locale.US).format(new Date()));
            date.setText(new SimpleDateFormat("EEEE, MMMM d", Locale.US).format(new Date()));
        } else if (type.equals("image")) {
            if (!card.optString("title").isEmpty()) body.addView(text(card.optString("title"), 24, white));
            body.addView(image(card.optString("image_path"), false), new LinearLayout.LayoutParams(-1, 0, 1));
        } else if (type.equals("html")) {
            web = new WebView(this); web.setBackgroundColor(background);
            web.getSettings().setJavaScriptEnabled(false); web.getSettings().setAllowFileAccess(false); web.getSettings().setAllowContentAccess(false);
            web.setWebViewClient(new WebViewClient() {
                public boolean shouldOverrideUrlLoading(WebView v, String u) { return true; }
                public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                    return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
                }
            });
            web.loadDataWithBaseURL(null, "<html><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{background:#161B19;color:#F1F0E7;font:24px sans-serif;margin:24px}</style>" + card.optString("html", "") + "</html>", "text/html", "UTF-8", null);
            body.addView(web, new LinearLayout.LayoutParams(-1, -1));
        } else {
            body.setPadding(dp(40), 0, dp(40), 0);
            body.addView(text(card.optString("eyebrow", "HERMES").toUpperCase(Locale.US), 14, color));
            TextView title = text(card.optString("title", ""), 52, white); title.setMaxLines(3); body.addView(title);
            ScrollView scroll = new ScrollView(this); TextView detail = text(card.optString("body", ""), 26, muted);
            detail.setLineSpacing(dp(5), 1); scroll.addView(detail); body.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        }
    }
    private ImageView image(String path, boolean thumbnail) {
        ImageView image = new ImageView(this); image.setScaleType(ImageView.ScaleType.FIT_CENTER); imageViews.add(image);
        File cached = imageFile(path);
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(cached.getPath(), options);
        options.inSampleSize = 1;
        int w = thumbnail ? 384 : 1280, h = thumbnail ? 200 : 800;
        while (options.outWidth / options.inSampleSize > w || options.outHeight / options.inSampleSize > h) options.inSampleSize *= 2;
        options.inJustDecodeBounds = false; options.inPreferredConfig = Bitmap.Config.RGB_565; options.inScaled = false;
        Bitmap bitmap = BitmapFactory.decodeFile(cached.getPath(), options);
        if (bitmap != null) { bitmaps.add(bitmap); image.setImageBitmap(bitmap); }
        else {
            if (OfflineAssets.cookbookPath(path)) invalidCookbookImages.add(path);
            image.setContentDescription("Waiting for cached image");
        }
        return image;
    }
    private void updateLibrary() {
        ArrayList<String> ids = new ArrayList<>(), categories = new ArrayList<>();
        for (int i = 0; i < recipes.length(); i++) { JSONObject r = recipes.optJSONObject(i); ids.add(r.optString("id")); categories.add(r.optString("category")); }
        library.update(ids, categories);
    }
    private JSONObject recipeById(String id) {
        for (int i = 0; i < recipes.length(); i++) if (recipes.optJSONObject(i).optString("id").equals(id)) return recipes.optJSONObject(i);
        return null;
    }
    private void renderLibrary() {
        updateLibrary();
        if (recipes.length() == 0) {
            body.addView(text("Cookbook is ready for your recipe library.", 28, white));
            body.addView(text("Once downloaded, the library and recipes stay available offline.", 21, muted)); return;
        }
        if (library.selected != null) {
            JSONObject r = recipeById(library.selected);
            body.addView(image(r.optString("detail_path"), false), new LinearLayout.LayoutParams(-1, 0, 1));
            LinearLayout footer = new LinearLayout(this);
            footer.addView(action("‹ Library", () -> { library.back(); render(); }), new LinearLayout.LayoutParams(0, dp(38), 1));
            footer.addView(action("‹ Previous", () -> swipe(-1))); footer.addView(action("Next ›", () -> swipe(1))); screen.addView(footer);
            return;
        }
        LinearLayout filters = new LinearLayout(this); filters.setGravity(Gravity.CENTER_VERTICAL);
        filters.addView(text("Category  ", 18, muted));
        TreeSet<String> categories = new TreeSet<>();
        for (int i = 0; i < recipes.length(); i++) categories.add(recipes.optJSONObject(i).optString("category"));
        ArrayList<String> options = new ArrayList<>(); options.add("All"); options.addAll(categories);
        if (!options.contains(library.category)) { library.filter("All"); updateLibrary(); }
        Spinner filter = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, options);
        filter.setAdapter(adapter); filter.setSelection(options.indexOf(library.category));
        filter.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> p, View view, int n, long id) {
                if (!library.category.equals(options.get(n))) { library.filter(options.get(n)); render(); }
            }
            public void onNothingSelected(AdapterView<?> p) {}
        });
        filters.addView(filter, new LinearLayout.LayoutParams(dp(260), dp(44)));
        filters.addView(text("  " + library.count() + " recipes · About 10–35 min · Serves 3", 18, muted));
        body.addView(filters);
        List<String> page = library.pageIds();
        for (int row = 0; row < 2; row++) {
            LinearLayout line = new LinearLayout(this);
            for (int column = 0; column < 4; column++) {
                int n = row * 4 + column;
                LinearLayout tile = new LinearLayout(this); tile.setOrientation(1); tile.setPadding(dp(6), dp(5), dp(6), dp(5));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -1, 1); lp.setMargins(dp(4), dp(4), dp(4), dp(4)); line.addView(tile, lp);
                if (n >= page.size()) continue;
                String id = page.get(n); JSONObject r = recipeById(id);
                tile.setBackground(rounded(Color.parseColor("#26302B"), 6));
                tile.addView(image(r.optString("thumbnail_path"), true), new LinearLayout.LayoutParams(-1, 0, 1));
                TextView title = text(r.optString("title"), 20, white); title.setMaxLines(3);
                title.setEllipsize(android.text.TextUtils.TruncateAt.END);
                tile.addView(title, new LinearLayout.LayoutParams(-1, dp(76)));
                tile.addView(text("About " + r.optInt("minutes") + " min · Representative photo", 12, muted));
                tile.setOnClickListener(v -> { library.choose(id); render(); });
            }
            body.addView(line, new LinearLayout.LayoutParams(-1, 0, 1));
        }
        LinearLayout footer = new LinearLayout(this); footer.setGravity(Gravity.CENTER_VERTICAL);
        footer.addView(action("‹ Previous", () -> swipe(-1)), new LinearLayout.LayoutParams(0, dp(38), 1));
        footer.addView(text("Page " + (library.page + 1) + " / " + library.pages(), 18, muted));
        footer.addView(action("Next ›", () -> swipe(1)), new LinearLayout.LayoutParams(0, dp(38), 1)); screen.addView(footer);
    }
    private void swipe(int delta) {
        if (tab.equals("Cookbook")) library.swipe(delta);
        else if (cards.length() > 0) { index = (index + delta + cards.length()) % cards.length(); rememberCard(); }
        render();
    }
    public boolean dispatchTouchEvent(MotionEvent e) {
        if (e.getAction() == MotionEvent.ACTION_DOWN) { downX = e.getX(); downY = e.getY(); }
        if (e.getAction() == MotionEvent.ACTION_UP) {
            float x = e.getX() - downX, y = e.getY() - downY;
            if (Math.abs(x) > dp(70) && Math.abs(x) > Math.abs(y) * 1.4) {
                // Cancel the original child touch so a swipe cannot also choose a tile.
                MotionEvent cancel = MotionEvent.obtain(e); cancel.setAction(MotionEvent.ACTION_CANCEL); super.dispatchTouchEvent(cancel); cancel.recycle();
                swipe(x < 0 ? 1 : -1); return true;
            }
        }
        return super.dispatchTouchEvent(e);
    }
    private void settings() {
        EditText field = new EditText(this); field.setText(base); field.setSingleLine();
        new AlertDialog.Builder(this).setTitle("Content source").setMessage("The address of your frame gateway. Changes take effect immediately.").setView(field)
            .setPositiveButton("Save", (d,w) -> {
                String next = field.getText().toString().replaceAll("/$", "");
                if (next.matches("http://[a-zA-Z0-9.:-]+")) {
                    base = next; cookbookCheck = 0; getPreferences(0).edit().putString("server", base).apply(); poll();
                } else Toast.makeText(this, "Enter an http:// address", 0).show();
            }).setNeutralButton("Original photos", (d,w) -> restorePhotos()).setNegativeButton("Cancel", null).show();
    }
    private void restorePhotos() {
        worker.execute(() -> {
            try {
                java.lang.Process proc = Runtime.getRuntime().exec("/system/xbin/su");
                try (OutputStream stream = proc.getOutputStream()) { stream.write("pm enable com.efercro.os.aimor\npm enable com.yhk.qeota\nexit\n".getBytes("UTF-8")); }
                if (proc.waitFor() != 0) throw new IOException("Unable to restore original app");
                handler.post(() -> {
                    android.content.Intent intent = getPackageManager().getLaunchIntentForPackage("com.efercro.os.aimor");
                    if (intent != null) startActivity(intent); else Toast.makeText(this, "Original app enabled. Restart the frame to open it.", 1).show();
                });
            } catch (Exception e) { handler.post(() -> Toast.makeText(this, "Could not open the original app.", 1).show()); }
        });
    }
    private void checkActive() throws IOException {
        if (destroyed || Thread.currentThread().isInterrupted()) throw new IOException("Cache sync cancelled");
    }
    private String read(InputStream in) throws IOException {
        try (InputStream stream = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] b = new byte[8192]; int n;
            while ((n = stream.read(b)) != -1) { checkActive(); out.write(b, 0, n); if (out.size() > 2 * 1024 * 1024) throw new IOException("Response too large"); }
            return new String(out.toByteArray(), "UTF-8");
        }
    }
    private HttpURLConnection connection(String path) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setConnectTimeout(4000); c.setReadTimeout(6000); c.setInstanceFollowRedirects(false);
        c.setRequestProperty("Authorization", "Bearer " + TOKEN); return c;
    }
    private File imageFile(String path) { return new File(getFilesDir(), "img-" + path.replaceAll("[^a-zA-Z0-9.-]", "_")); }
    private void cacheImage(String path, boolean libraryAsset, boolean thumbnail) throws Exception {
        if (!(libraryAsset ? OfflineAssets.cookbookPath(path) : path.matches("/media/[a-f0-9]{64}\\.(png|jpg|webp)"))) throw new IOException("Invalid image path");
        // Serialize cache admission, writes and trim, including across Activity instances.
        synchronized (OfflineAssets.class) {
            checkActive();
            File target = imageFile(path);
            if (target.isFile() && !(libraryAsset && invalidCookbookImages.contains(path))) {
                try { if (libraryAsset) verifyImage(target, path, thumbnail); return; }
                catch (Exception e) { /* Keep the existing file until a verified replacement is ready. */ }
            }
            final int limit = libraryAsset ? cookbookAssetLimit : deckAssetLimit;
            OfflineAssets.stage(target, limit, cacheLimitBytes, tmp -> {
                // Budget admission occurs before opening the connection or writing any bytes.
                HttpURLConnection conn = connection(path);
                try {
                    try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(tmp)) {
                        byte[] b = new byte[8192]; int n, total = 0;
                        while ((n = in.read(b)) != -1) {
                            checkActive();
                            if (n > limit - total) throw new IOException("Image too large");
                            total += n; out.write(b, 0, n);
                        }
                        out.getFD().sync();
                    }
                } finally { conn.disconnect(); }
            }, libraryAsset ? tmp -> verifyImage(tmp, path, thumbnail) : null);
            if (libraryAsset) invalidCookbookImages.remove(path);
        }
    }
    private void verifyImage(File file, String path, boolean thumbnail) throws Exception {
        OfflineAssets.verify(file, path);
        BitmapFactory.Options o = new BitmapFactory.Options(); o.inJustDecodeBounds = true; BitmapFactory.decodeFile(file.getPath(), o);
        if (o.outWidth != (thumbnail ? 384 : 1280) || o.outHeight != (thumbnail ? 200 : 800)) throw new IOException("Invalid cookbook dimensions");
    }
    private boolean cacheDeck(JSONArray arr) throws Exception {
        boolean repaired = false;
        for (int i = 0; i < arr.length(); i++) {
            checkActive();
            JSONObject c = arr.getJSONObject(i);
            if (c.optString("type").equals("image")) {
                String path = c.getString("image_path");
                if (!imageFile(path).isFile()) repaired = true;
                cacheImage(path, false, false);
            }
        }
        return repaired;
    }
    private boolean syncDeck(JSONObject incoming) throws Exception {
        JSONArray next = incoming.getJSONArray("cards");
        if (next.length() < 1 || next.length() > 20) throw new IOException("Invalid cards");
        incoming.getLong("revision");
        // Retain incoming assets until the authoritative index is durable. Activity
        // recreation can leave an old worker running alongside a new one's trim.
        synchronized (OfflineAssets.class) {
            checkActive();
            boolean repaired = cacheDeck(next);
            save("state.json", incoming);
            return repaired;
        }
    }
    private void save(String name, JSONObject data) throws Exception {
        File target = new File(getFilesDir(), name);
        checkActive();
        String encoded = data.toString();
        try { if (target.isFile() && encoded.equals(read(new FileInputStream(target)))) return; }
        catch (IOException e) { /* Replace a truncated/oversized saved index on recovery. */ }
        byte[] bytes = encoded.getBytes("UTF-8");
        checkActive();
        OfflineAssets.stage(target, bytes.length, cacheLimitBytes, tmp -> {
            try (FileOutputStream out = new FileOutputStream(tmp)) { out.write(bytes); out.getFD().sync(); }
        }, null);
    }
    private void validateCookbook(JSONObject incoming) throws Exception {
        JSONArray arr = incoming.getJSONArray("recipes");
        if (incoming.getInt("version") != 1 || arr.length() > 50 || incoming.toString().length() > 512 * 1024) throw new IOException("Invalid cookbook");
        if (!incoming.getString("revision").matches("empty|[a-f0-9]{64}")) throw new IOException("Invalid cookbook revision");
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject r = arr.getJSONObject(i);
            if (!r.getString("id").matches("[a-zA-Z0-9_-]{1,64}") || !ids.add(r.getString("id")) || r.getString("title").length() > 90 || r.getString("category").length() > 32 || !r.getBoolean("photo_representative")) throw new IOException("Invalid recipe");
            if (!OfflineAssets.cookbookPath(r.getString("detail_path")) || !OfflineAssets.cookbookPath(r.getString("thumbnail_path"))) throw new IOException("Invalid recipe images");
        }
    }
    private void syncCookbook() throws Exception {
        HttpURLConnection conn = connection("/cookbook"); JSONObject incoming;
        try { incoming = new JSONObject(read(conn.getInputStream())); } finally { conn.disconnect(); }
        validateCookbook(incoming);
        JSONArray arr = incoming.getJSONArray("recipes");
        final boolean repaired;
        // Verification, downloads and index publication are one trim-free transaction.
        synchronized (OfflineAssets.class) {
            checkActive();
            boolean complete = new File(getFilesDir(), "cookbook.json").isFile();
            for (int i = 0; complete && i < arr.length(); i++) {
                checkActive();
                JSONObject r = arr.getJSONObject(i);
                for (String key : new String[]{"thumbnail_path", "detail_path"}) {
                    String path = r.getString(key);
                    if (invalidCookbookImages.contains(path)) { complete = false; break; }
                    // Recheck bytes and decoded bounds every sync, including process startup
                    // and same-length changes made after a previous successful verification.
                    try { verifyImage(imageFile(path), path, key.equals("thumbnail_path")); }
                    catch (Exception e) { complete = false; break; }
                }
            }
            if (complete && incoming.optString("revision").equals(cookbook.optString("revision"))) return;
            repaired = !complete;
            for (int i = 0; i < arr.length(); i++) {
                checkActive();
                JSONObject r = arr.getJSONObject(i);
                cacheImage(r.getString("thumbnail_path"), true, true); cacheImage(r.getString("detail_path"), true, false);
            }
            // Keep the old offline index until ALL assets are verified and durable.
            save("cookbook.json", incoming);
        }
        handler.post(() -> {
            if (destroyed) return;
            boolean changed = !incoming.optString("revision").equals(cookbook.optString("revision"));
            cookbook = incoming; recipes = arr;
            if ((changed || repaired) && tab.equals("Cookbook")) render();
        });
    }
    private void trimCache() throws Exception {
        synchronized (OfflineAssets.class) {
            checkActive();
            Set<String> keep = new HashSet<>();
            try { JSONArray all = load("state.json").getJSONArray("cards");
                for (int i = 0; i < all.length(); i++) { String p = all.getJSONObject(i).optString("image_path"); if (!p.isEmpty()) keep.add(imageFile(p).getName()); }
            } catch (Exception e) { /* Corrupt/missing index must not prevent a recovery poll. */ }
            try { JSONArray all = load("cookbook.json").getJSONArray("recipes");
                for (int i = 0; i < all.length(); i++) for (String key : new String[]{"thumbnail_path", "detail_path"}) keep.add(imageFile(all.getJSONObject(i).getString(key)).getName());
            } catch (Exception e) { /* The other complete collection remains independently usable. */ }
            // Cancellation during index reads must never turn a partial keep set
            // into permission to delete an authoritative collection's assets.
            checkActive();
            OfflineAssets.trim(getFilesDir(), keep);
        }
    }
    private void poll() {
        if (busy || destroyed) return; busy = true;
        worker.execute(() -> {
            try {
                trimCache();
                HttpURLConnection conn = connection("/state"); JSONObject incoming;
                try { incoming = new JSONObject(read(conn.getInputStream())); } finally { conn.disconnect(); }
                boolean repaired = syncDeck(incoming); long rev = incoming.getLong("revision");
                handler.post(() -> {
                    if (destroyed) return; connected = true;
                    if (rev != revision) {
                        rememberCard(); state = incoming; revision = rev;
                        String wanted = incoming.optString("focus_id");
                        if (!wanted.isEmpty()) {
                            if (LibraryNavigation.weekly(wanted)) { weekId = wanted; tab = "This Week"; }
                            else { photoId = wanted; tab = "Photos"; }
                        }
                        render();
                    } else if (repaired && !tab.equals("Cookbook")) render();
                    status.setText("● CONNECTED"); status.setTextColor(color);
                });
                // Independent cookbook failure never discards the working deck/cache.
                if (System.currentTimeMillis() - cookbookCheck > 30000) {
                    cookbookCheck = System.currentTimeMillis();
                    try { syncCookbook(); }
                    catch (Exception e) { handler.post(() -> { if (!destroyed && tab.equals("Cookbook")) status.setText("SAVED COOKBOOK · SYNC PENDING"); }); }
                }
            } catch (Exception e) {
                handler.post(() -> { if (!destroyed) { connected = false; status.setText("OFFLINE · SAVED CONTENT"); status.setTextColor(muted); } });
            } finally {
                // Defer deletion until queued UI updates have detached the previous screen.
                handler.post(() -> {
                    if (destroyed) return;
                    worker.execute(() -> { try { trimCache(); } catch (Exception e) {} handler.post(() -> busy = false); });
                });
            }
        });
    }
    protected void onDestroy() {
        destroyed = true; handler.removeCallbacksAndMessages(null); worker.shutdownNow();
        if (web != null) web.destroy(); if (screen != null) screen.removeAllViews(); releaseImages(); super.onDestroy();
    }
    public void onBackPressed() { if (tab.equals("Cookbook") && library.selected != null) { library.back(); render(); } }
}
