package android.graphics;
import java.io.File;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
/** Real host PNG decoder supplies the Android bounds API used by production verification. */
public class BitmapFactory {
    public static class Options {
        public boolean inJustDecodeBounds, inScaled;
        public int outWidth = -1, outHeight = -1, inSampleSize;
        public Bitmap.Config inPreferredConfig;
    }
    public static Bitmap decodeFile(String path, Options options) {
        try {
            BufferedImage image = ImageIO.read(new File(path));
            if (image != null) { options.outWidth = image.getWidth(); options.outHeight = image.getHeight(); }
        } catch (Exception e) { options.outWidth = options.outHeight = -1; }
        return null;
    }
}
