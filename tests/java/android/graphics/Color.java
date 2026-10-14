package android.graphics;
public class Color {
    public static int parseColor(String value) { return (int) Long.parseLong(value.substring(1), 16); }
}
