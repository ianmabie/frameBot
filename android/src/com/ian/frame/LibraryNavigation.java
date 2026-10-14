package com.ian.frame;

import java.util.*;

/** Pure logical navigation: no network calls or Android/bitmap dependencies. */
final class LibraryNavigation {
    static final int PAGE_SIZE = 8;
    String category = "All";
    int page = 0;
    String selected = null;
    private final List<String> visible = new ArrayList<>();

    static boolean weekly(String id) {
        return "dinner-week".equals(id) || id.matches("recipe-(mon|tue|wed|thu|fri|sat|sun)");
    }

    void update(List<String> ids, List<String> categories) {
        visible.clear();
        for (int i = 0; i < ids.size(); i++)
            if (category.equals("All") || category.equals(categories.get(i))) visible.add(ids.get(i));
        page = Math.max(0, Math.min(page, pages() - 1));
        if (!visible.contains(selected)) selected = null;
    }

    void filter(String value) { category = value; page = 0; selected = null; }
    int pages() { return Math.max(1, (visible.size() + PAGE_SIZE - 1) / PAGE_SIZE); }
    int count() { return visible.size(); }
    List<String> pageIds() {
        int start = page * PAGE_SIZE;
        return new ArrayList<>(visible.subList(start, Math.min(start + PAGE_SIZE, visible.size())));
    }
    void choose(String id) { if (visible.contains(id)) selected = id; }
    void back() { selected = null; }
    void swipe(int delta) {
        if (selected == null) page = (page + delta + pages()) % pages();
        else selected = visible.get((visible.indexOf(selected) + delta + visible.size()) % visible.size());
    }
}
