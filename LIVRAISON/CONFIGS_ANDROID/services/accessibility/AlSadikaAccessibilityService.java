package ai.alsadika.app.accessibility;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.content.Intent;
import android.util.Log;

public class AlSadikaAccessibilityService extends AccessibilityService {
    private static final String TAG = "AlSadikaAccessibility";
    private static AlSadikaAccessibilityService instance;

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Log events for debugging
        Log.d(TAG, "Accessibility event: " + event.getEventType());
    }

    @Override
    public void onInterrupt() {
        Log.d(TAG, "Accessibility service interrupted");
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        Log.d(TAG, "Al Sâdika Accessibility Service connected");
    }

    @Override
    public boolean onUnbind(Intent intent) {
        instance = null;
        Log.d(TAG, "Al Sâdika Accessibility Service disconnected");
        return super.onUnbind(intent);
    }

    public static AlSadikaAccessibilityService getInstance() {
        return instance;
    }

    public boolean performClick(int x, int y) {
        try {
            Path clickPath = new Path();
            clickPath.moveTo(x, y);
            
            GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(clickPath, 0, 100));
            
            return dispatchGesture(gestureBuilder.build(), null, null);
        } catch (Exception e) {
            Log.e(TAG, "Error performing click", e);
            return false;
        }
    }

    public boolean performScroll(int startX, int startY, int endX, int endY) {
        try {
            Path scrollPath = new Path();
            scrollPath.moveTo(startX, startY);
            scrollPath.lineTo(endX, endY);
            
            GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(scrollPath, 0, 500));
            
            return dispatchGesture(gestureBuilder.build(), null, null);
        } catch (Exception e) {
            Log.e(TAG, "Error performing scroll", e);
            return false;
        }
    }

    public boolean performTextInput(String text) {
        try {
            AccessibilityNodeInfo focused = findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (focused != null && focused.isEditable()) {
                focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, 
                    android.os.Bundle.EMPTY);
                return true;
            }
            return false;
        } catch (Exception e) {
            Log.e(TAG, "Error performing text input", e);
            return false;
        }
    }
}