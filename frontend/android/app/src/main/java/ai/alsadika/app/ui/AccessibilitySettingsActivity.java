package ai.alsadika.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;

public class AccessibilitySettingsActivity extends Activity {
    private static final String TAG = "AccessibilitySettings";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.d(TAG, "Opening accessibility settings for Al Sâdika");
        
        // Redirect to system accessibility settings
        Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
        startActivity(intent);
        finish();
    }
}