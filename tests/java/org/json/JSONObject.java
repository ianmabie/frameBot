package org.json;
import java.util.*;
/** Small host JSON implementation; production sync/cache algorithms remain unmodified. */
public class JSONObject {
    final Map<String, Object> values = new LinkedHashMap<>();
    public JSONObject() {}
    public JSONObject(String text) { values.putAll(((JSONObject) new Parser(text).parse()).values); }
    public JSONObject put(String key, Object value) { values.put(key, value); return this; }
    public Object get(String key) { if (!values.containsKey(key)) throw new IllegalArgumentException(key); return values.get(key); }
    public String getString(String key) { return (String) get(key); }
    public int getInt(String key) { return ((Number) get(key)).intValue(); }
    public long getLong(String key) { return ((Number) get(key)).longValue(); }
    public boolean getBoolean(String key) { return (Boolean) get(key); }
    public JSONArray getJSONArray(String key) { return (JSONArray) get(key); }
    public JSONArray optJSONArray(String key) { Object value = values.get(key); return value instanceof JSONArray ? (JSONArray) value : null; }
    public String optString(String key) { return optString(key, ""); }
    public String optString(String key, String fallback) { Object value = values.get(key); return value instanceof String ? (String) value : fallback; }
    public int optInt(String key) { Object value = values.get(key); return value instanceof Number ? ((Number) value).intValue() : 0; }
    public long optLong(String key, long fallback) { Object value = values.get(key); return value instanceof Number ? ((Number) value).longValue() : fallback; }
    public String toString() { return encode(values); }
    static String encode(Object value) {
        if (value instanceof JSONObject) return value.toString();
        if (value instanceof JSONArray) return value.toString();
        if (value instanceof String) return "\"" + ((String) value).replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\"";
        if (value instanceof Map) {
            List<String> parts = new ArrayList<>();
            for (Map.Entry<?, ?> e : ((Map<?, ?>) value).entrySet()) parts.add(encode(e.getKey()) + ":" + encode(e.getValue()));
            return "{" + String.join(",", parts) + "}";
        }
        if (value instanceof List) {
            List<String> parts = new ArrayList<>(); for (Object item : (List<?>) value) parts.add(encode(item));
            return "[" + String.join(",", parts) + "]";
        }
        return String.valueOf(value);
    }
    static final class Parser {
        final String text; int at;
        Parser(String text) { this.text = text; }
        Object parse() { Object value = value(); space(); if (at != text.length()) throw new IllegalArgumentException("trailing JSON"); return value; }
        void space() { while (at < text.length() && Character.isWhitespace(text.charAt(at))) at++; }
        boolean take(char c) { space(); if (at < text.length() && text.charAt(at) == c) { at++; return true; } return false; }
        void need(char c) { if (!take(c)) throw new IllegalArgumentException("expected " + c); }
        Object value() {
            space(); char c = text.charAt(at);
            if (c == '"') return string();
            if (take('{')) {
                JSONObject result = new JSONObject(); if (take('}')) return result;
                do { String key = string(); need(':'); result.put(key, value()); } while (take(',')); need('}'); return result;
            }
            if (take('[')) {
                JSONArray result = new JSONArray(); if (take(']')) return result;
                do { result.put(value()); } while (take(',')); need(']'); return result;
            }
            int start = at; while (at < text.length() && ",]} \t\r\n".indexOf(text.charAt(at)) == -1) at++;
            String token = text.substring(start, at);
            if (token.equals("true")) return true; if (token.equals("false")) return false; if (token.equals("null")) return null;
            return Long.parseLong(token);
        }
        String string() {
            need('"'); StringBuilder result = new StringBuilder();
            while (at < text.length()) {
                char c = text.charAt(at++); if (c == '"') return result.toString();
                if (c == '\\') {
                    c = text.charAt(at++);
                    if (c == 'u') { c = (char) Integer.parseInt(text.substring(at, at + 4), 16); at += 4; }
                    else if (c == 'n') c = '\n'; else if (c == 'r') c = '\r'; else if (c == 't') c = '\t';
                }
                result.append(c);
            }
            throw new IllegalArgumentException("unterminated JSON string");
        }
    }
}
