package ai.alsadika.app.totalcontrol;

import android.util.Log;
import com.getcapacitor.Plugin;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.JSObject;
import com.getcapacitor.annotation.PluginMethod;

@CapacitorPlugin(name = "TotalControl")
public class TotalControl extends Plugin {
    @PluginMethod
    public void enableControl(com.getcapacitor.PluginCall call) {
        Log.i("TotalControl","enableControl (stub)");
        JSObject ret = new JSObject();
        ret.put("enabled", true);
        call.resolve(ret);
    }

    @PluginMethod
    public void disableControl(com.getcapacitor.PluginCall call) {
        Log.i("TotalControl","disableControl (stub)");
        JSObject ret = new JSObject();
        ret.put("enabled", false);
        call.resolve(ret);
    }

    @PluginMethod
    public void status(com.getcapacitor.PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("enabled", false);
        call.resolve(ret);
    }
}
