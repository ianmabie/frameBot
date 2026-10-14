package android.app;
import java.io.File;
/** Host framework shim: no UI is exercised by the cache regressions. */
public class Activity extends android.content.Context {
    public File getFilesDir() { throw new UnsupportedOperationException(); }
    public void onCreate(android.os.Bundle saved) {}
    protected void onDestroy() {}
    public void onBackPressed() {}
    public boolean dispatchTouchEvent(android.view.MotionEvent event) { return false; }
    public android.view.Window getWindow() { throw new UnsupportedOperationException(); }
    public android.content.SharedPreferences getPreferences(int mode) { throw new UnsupportedOperationException(); }
    public android.content.res.Resources getResources() { throw new UnsupportedOperationException(); }
    public android.content.pm.PackageManager getPackageManager() { throw new UnsupportedOperationException(); }
    public void startActivity(android.content.Intent intent) { throw new UnsupportedOperationException(); }
    public void setContentView(android.view.View view) { throw new UnsupportedOperationException(); }
}
