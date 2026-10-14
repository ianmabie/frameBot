package com.ian.frame;

import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Bounded file-only cache. Decoding is confined to the current visible screen. */
final class OfflineAssets {
    static final int MAX_COOKBOOK_ASSET = 1536 * 1024;
    // Combined committed/staged images and indices, including interrupted .tmp files.
    static final long MAX_CACHE_BYTES = 480L * 1024 * 1024;
    static boolean cookbookPath(String path) {
        return path.matches("/cookbook/assets/[a-f0-9]{64}\\.png");
    }
    static void verify(File file, String path) throws Exception {
        if (!cookbookPath(path) || file.length() < 1 || file.length() > MAX_COOKBOOK_ASSET)
            throw new IOException("Invalid cookbook asset");
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(file)) {
            byte[] buffer = new byte[8192]; int n;
            while ((n = in.read(buffer)) != -1) digest.update(buffer, 0, n);
        }
        StringBuilder hash = new StringBuilder();
        for (byte b : digest.digest()) hash.append(String.format(Locale.US, "%02x", b & 255));
        if (!path.equals("/cookbook/assets/" + hash + ".png")) throw new IOException("Cookbook hash mismatch");
    }
    interface StageWriter { void write(File staged) throws Exception; }
    interface StageVerifier { void verify(File staged) throws Exception; }
    private static long diskBytes(File directory) throws IOException {
        File[] files = directory.listFiles();
        if (files == null) throw new IOException("Cannot inspect offline cache");
        long total = 0;
        for (File file : files) {
            String name = file.getName();
            if (name.startsWith("img-") || name.equals("state.json") || name.equals("cookbook.json")
                    || name.equals("state.json.tmp") || name.equals("cookbook.json.tmp")) total += file.length();
        }
        return total;
    }
    /** Admission and the entire write/verify/rename share trim's lock. No pre-deletion. */
    static synchronized void stage(File target, long maximum, long budget,
                                  StageWriter writer, StageVerifier verifier) throws Exception {
        long used = diskBytes(target.getParentFile());
        if (maximum < 0 || maximum > budget - used) throw new IOException("Offline cache limit exceeded");
        File staged = new File(target.getPath() + ".tmp");
        try {
            writer.write(staged);
            if (staged.length() > maximum) throw new IOException("Staged file too large");
            if (verifier != null) verifier.verify(staged);
            if (!staged.renameTo(target)) throw new IOException("Cache replacement failed");
        } finally {
            if (staged.exists() && !staged.delete()) throw new IOException("Cache staging cleanup failed");
        }
    }
    static synchronized void trim(File directory, Set<String> keep) throws IOException {
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File f : files) {
            String name = f.getName();
            boolean interruptedIndex = name.equals("state.json.tmp") || name.equals("cookbook.json.tmp");
            if (!name.startsWith("img-") && !interruptedIndex) continue;
            if (interruptedIndex || !keep.contains(name)) {
                if (!f.delete() && f.exists()) throw new IOException("Cache cleanup failed");
            }
        }
        if (diskBytes(directory) > MAX_CACHE_BYTES) throw new IOException("Offline cache limit exceeded");
    }
}
