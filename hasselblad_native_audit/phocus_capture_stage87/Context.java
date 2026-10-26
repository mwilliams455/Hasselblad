package android.content;
import java.util.*;
/** Test adapter: isolated preference namespaces and failed commits, not Android storage. */
public final class Context {
    public static final int MODE_PRIVATE=0;
    private final Map<String,Prefs> stores=new HashMap<>();
    public boolean fail,failUpdatesMemory;
    public Prefs getSharedPreferences(String name,int mode){return stores.computeIfAbsent(name,k->new Prefs());}
    public final class Prefs {
        private final Map<String,Object> values=new HashMap<>();
        private final Map<String,Object> disk=new HashMap<>();
        public boolean getBoolean(String key,boolean fallback){return (boolean)values.getOrDefault(key,fallback);}
        public String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}
        public void reload(){values.clear();values.putAll(disk);}
        public Editor edit(){return new Editor(this);}
    }
    public final class Editor {
        private final Prefs prefs;private String key;private Object value;
        Editor(Prefs prefs){this.prefs=prefs;}
        public Editor putBoolean(String key,boolean value){this.key=key;this.value=value;return this;}
        public Editor putString(String key,String value){this.key=key;this.value=value;return this;}
        public boolean commit(){if(!fail||failUpdatesMemory)prefs.values.put(key,value);if(fail)return false;prefs.disk.put(key,value);return true;}
    }
}
