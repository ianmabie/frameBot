package com.ian.frame;

import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Executable tests against production navigation and cache code, without Android. */
public final class CookbookLogicTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        LibraryNavigation n = new LibraryNavigation();
        List<String> ids = new ArrayList<>(), categories = new ArrayList<>();
        for (int i = 0; i < 50; i++) { ids.add("r" + i); categories.add(i % 2 == 0 ? "Beans" : "Fish"); }
        n.update(ids, categories);
        check(n.count() == 50 && n.pages() == 7 && n.pageIds().size() == 8, "50 recipes in seven bounded pages");
        n.swipe(-1); check(n.page == 6 && n.pageIds().size() == 2, "page wrap and short last page");
        n.choose("r48"); n.swipe(1); check(n.selected.equals("r49"), "detail swipe");
        n.swipe(1); check(n.selected.equals("r0"), "detail wrap");
        n.back(); check(n.selected == null && n.page == 6, "back preserves library page");
        n.filter("Beans"); n.update(ids, categories);
        check(n.count() == 25 && n.pages() == 4 && n.page == 0, "category filter");
        n.choose("r1"); check(n.selected == null, "cannot select filtered-out recipe");
        n.choose("r0"); n.update(ids.subList(2, 50), categories.subList(2, 50));
        check(n.selected == null, "revision removal clears selection");
        n.filter("Absent"); n.update(ids, categories); n.swipe(1);
        check(n.pages() == 1 && n.pageIds().isEmpty(), "empty filter safe");
        check(LibraryNavigation.weekly("dinner-week") && LibraryNavigation.weekly("recipe-mon"), "weekly stable IDs");
        check(!LibraryNavigation.weekly("photo-pair") && !LibraryNavigation.weekly("sample-recipe-1"), "existing photos/previews retained");

        Path directory = Files.createTempDirectory("frame-cache-");
        try {
            byte[] bytes = "synthetic cached file".getBytes("UTF-8");
            StringBuilder hash = new StringBuilder();
            for (byte b : MessageDigest.getInstance("SHA-256").digest(bytes)) hash.append(String.format(Locale.US, "%02x", b & 255));
            String path = "/cookbook/assets/" + hash + ".png";
            File asset = directory.resolve("img-active").toFile(); Files.write(asset.toPath(), bytes);
            OfflineAssets.verify(asset, path);
            Files.write(directory.resolve("img-obsolete"), bytes);
            Files.write(directory.resolve("img-interrupted.tmp"), bytes);
            Files.write(directory.resolve("state.json"), bytes);
            OfflineAssets.trim(directory.toFile(), new HashSet<>(Arrays.asList("img-active")));
            check(asset.exists() && Files.exists(directory.resolve("state.json")), "offline cache preserves active assets/index");
            check(!Files.exists(directory.resolve("img-obsolete")) && !Files.exists(directory.resolve("img-interrupted.tmp")), "obsolete and interrupted assets pruned");
            Files.write(asset.toPath(), "changed".getBytes("UTF-8"));
            boolean rejected = false;
            try { OfflineAssets.verify(asset, path); } catch (IOException e) { rejected = true; }
            check(rejected, "corrupt cached asset rejected");
            check(!OfflineAssets.cookbookPath("/cookbook/assets/../secret.png"), "path traversal rejected");
            check(OfflineAssets.MAX_COOKBOOK_ASSET == 1536 * 1024 && OfflineAssets.MAX_CACHE_BYTES == 480L * 1024 * 1024, "bounded cache constants");
        } finally {
            for (File f : directory.toFile().listFiles()) f.delete(); directory.toFile().delete();
        }
        System.out.println("Cookbook navigation and offline cache tests passed (50 recipes).");
    }
}
