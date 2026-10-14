package org.json;
import java.util.*;
public class JSONArray {
    final List<Object> values = new ArrayList<>();
    public JSONArray put(Object value) { values.add(value); return this; }
    public int length() { return values.size(); }
    public JSONObject getJSONObject(int index) { return (JSONObject) values.get(index); }
    public JSONObject optJSONObject(int index) { return index >= 0 && index < values.size() && values.get(index) instanceof JSONObject ? (JSONObject) values.get(index) : null; }
    public String toString() { return JSONObject.encode(values); }
}
