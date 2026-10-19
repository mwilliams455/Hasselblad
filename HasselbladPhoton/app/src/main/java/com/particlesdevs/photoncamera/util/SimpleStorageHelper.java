package com.particlesdevs.photoncamera.util;

import android.content.Context;
import android.os.Environment;
import android.os.ParcelFileDescriptor;

import androidx.documentfile.provider.DocumentFile;

import com.anggrayudi.storage.file.DocumentFileCompat;
import com.anggrayudi.storage.file.DocumentFileType;
import com.anggrayudi.storage.file.FileFullPath;
import com.anggrayudi.storage.file.StorageId;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Wrapper around SimpleStorage library for folder access and path resolution.
 * Uses DCIM/HasselbladPhoton as the target path; persists via SAF so export/import and native writing work.
 *
 * <p>Call {@link #init(Context)} once from {@code PhotonCamera.initModules()} so all
 * methods can operate without a per-call Context parameter.
 *
 * @see <a href="https://github.com/anggrayudi/SimpleStorage">SimpleStorage</a>
 */
public final class SimpleStorageHelper {

    private static final String TAG = "SimpleStorageHelper";

    private static Context sContext;

    /** Initialize the module. Call once from {@code PhotonCamera.initModules()}. */
    public static void init(Context context) {
        sContext = context.getApplicationContext();
    }

    /** Base path we request access to (picker opens here when supported). */
    public static final String DCIM_BASE_PATH = "DCIM";

    /** Relative path for settings backup/restore. */
    public static final String PHOTON_CAMERA_RELATIVE_PATH = FileManager.APP_STORAGE_RELATIVE_PATH;

    /** True if a SAF grant covers primary DCIM, including this app's folder and Camera JPEGs. */
    public static boolean hasStorageAccess(Context context) {
        if (context == null) return false;
        try {
            Map<String, Set<String>> pathMap = DocumentFileCompat.getAccessibleAbsolutePaths(context);
            if (pathMap == null || pathMap.isEmpty()) return false;
            String dcimPath = new File(Environment.getExternalStorageDirectory(),
                    DCIM_BASE_PATH).getCanonicalPath();
            for (Set<String> paths : pathMap.values()) {
                if (paths == null) continue;
                for (String path : paths) {
                    if (path == null || !new File(path).isAbsolute()) continue;
                    String grantedPath = new File(path).getCanonicalPath();
                    String prefix = grantedPath.endsWith(File.separator)
                            ? grantedPath : grantedPath + File.separator;
                    if (dcimPath.equals(grantedPath) || dcimPath.startsWith(prefix)) {
                        return true;
                    }
                }
            }
            return false;
        } catch (Throwable t) {
            Log.e(TAG, "hasStorageAccess: " + t.getMessage());
            return false;
        }
    }

    /**
     * Gets DCIM/HasselbladPhoton for backup/restore. Returns null if no access.
     */
    public static DocumentFile getPhotonCameraFolder(Context context) {
        if (!SimpleStorageHelper.hasStorageAccess(context)) {
            return null;
        }
        return DocumentFileCompat.fromSimplePath(
                context,
                StorageId.PRIMARY,
                SimpleStorageHelper.PHOTON_CAMERA_RELATIVE_PATH,
                DocumentFileType.FOLDER,
                true
        );
    }

    /** Lists .json and .xml backup file names in DCIM/HasselbladPhoton. */
    public static String[] listBackupFileNames(Context context) {
        DocumentFile folder = getPhotonCameraFolder(context);
        if (folder == null || !folder.exists()) return new String[0];
        DocumentFile[] files = folder.listFiles();
        if (files == null) return new String[0];
        List<String> names = new ArrayList<>();
        for (DocumentFile f : files) {
            if (f == null || f.isDirectory()) continue;
            String name = f.getName();
            if (name != null && (name.endsWith(".json") || name.endsWith(".xml")))
                names.add(name);
        }
        names.sort(String::compareToIgnoreCase);
        return names.toArray(new String[0]);
    }

    /** Opens an OutputStream to create/overwrite a file in DCIM/HasselbladPhoton. Caller must close it. */
    public static OutputStream openOutputStream(Context context, String fileName) throws Exception {
        DocumentFile folder = getPhotonCameraFolder(context);
        if (folder == null || !folder.exists())
            throw new SecurityException("No storage access to " + PHOTON_CAMERA_RELATIVE_PATH);
        if (fileName == null || fileName.isEmpty())
            throw new IllegalArgumentException("fileName is empty");
        DocumentFile file = folder.findFile(fileName);
        if (file != null && file.exists()) file.delete();
        file = folder.createFile("application/json", fileName);
        if (file == null) throw new IOException("Failed to create file: " + fileName);
        OutputStream os = context.getContentResolver().openOutputStream(file.getUri(), "w");
        if (os == null) throw new IOException("Failed to open output stream for: " + fileName);
        return os;
    }

    /** Opens an InputStream to read a file from DCIM/HasselbladPhoton. Caller must close it. */
    public static InputStream openInputStream(Context context, String fileName) throws Exception {
        return openInputStreamByPath(context, PHOTON_CAMERA_RELATIVE_PATH + "/" + fileName);
    }

    /** Keeps standalone paths on primary DCIM after verifying the grant covers that directory. */
    public static void updateFileManagerPaths(Context context) {
        if (context == null || !hasStorageAccess(context)) return;
        try {
            File dcimDirectory = new File(Environment.getExternalStorageDirectory(), DCIM_BASE_PATH);
            FileManager.sDCIM_CAMERA = new File(dcimDirectory, "Camera");
            FileManager.sPHOTON_DIR = new File(dcimDirectory, FileManager.APP_STORAGE_FOLDER);
            FileManager.sPHOTON_RAW_DIR = new File(FileManager.sPHOTON_DIR, "Raw");
            FileManager.sPHOTON_TUNING_DIR = new File(FileManager.sPHOTON_DIR, "Tuning");
            Log.d(TAG, "Standalone paths: " + FileManager.sPHOTON_DIR);
        } catch (Throwable t) {
            Log.e(TAG, "updateFileManagerPaths: " + t.getMessage());
        }
    }

    /** True if a file at the given path (relative to primary storage root) exists and is accessible. */
    public static boolean fileExistsByPath(Context context, String relativePath) {
        try {
            DocumentFile file = DocumentFileCompat.INSTANCE.fromSimplePath(context, StorageId.PRIMARY, relativePath);
            return file != null && file.exists();
        } catch (Throwable t) {
            Log.e(TAG, "fileExistsByPath: " + t.getMessage());
            return false;
        }
    }

    /** Opens an InputStream for a file at the given path relative to primary storage root. Caller must close it. */
    public static InputStream openInputStreamByPath(Context context, String relativePath) throws Exception {
        DocumentFile file = DocumentFileCompat.INSTANCE.fromSimplePath(context, StorageId.PRIMARY, relativePath);
        if (file == null || !file.exists())
            throw new java.io.FileNotFoundException("File not found: " + relativePath);
        InputStream is = context.getContentResolver().openInputStream(file.getUri());
        if (is == null) throw new IOException("Failed to open stream for: " + relativePath);
        return is;
    }

    /** Builds the initial path for RequestStorageAccessContract so the picker opens at DCIM. */
    public static FileFullPath createDcimInitialPath(Context context) {
        return new FileFullPath(context, StorageId.PRIMARY, DCIM_BASE_PATH);
    }

    /**
     * Creates a file at {@code absolutePath} via SAF and returns a detached raw POSIX fd for
     * native writing. Required on Android 11+ where the FUSE MediaProvider blocks {@code fopen()}
     * for non-image file types (e.g. {@code .flac}) inside DCIM directories.
     *
     * <p>SimpleStorage's {@code fromSimplePath} automatically resolves the SAF-granted tree and
     * navigates to any subdirectory under the granted root — no manual tree walking needed.
     *
     * @return raw file descriptor ≥ 0, or -1 on failure
     */
    public static int openFdForWrite(String absolutePath) {
        if (sContext == null || absolutePath == null) return -1;
        try {
            DocumentFile newFile = createDocumentFile(absolutePath);
            if (newFile == null) return -1;

            ParcelFileDescriptor pfd = sContext.getContentResolver()
                    .openFileDescriptor(newFile.getUri(), "w");
            if (pfd == null) return -1;
            return pfd.detachFd();

        } catch (Exception e) {
            Log.e(TAG, "openFdForWrite: " + e.getMessage());
            return -1;
        }
    }

    /**
     * Creates a file at {@code absolutePath} via SAF and returns an {@link OutputStream} for
     * Java-side writing (text, JSON, CSV, etc.). Required on Android 11+ for the same FUSE
     * reasons as {@link #openFdForWrite}.
     *
     * <p>Falls back to {@code null} on failure; callers should fall back to
     * {@link java.nio.file.Files#newOutputStream} for app-specific directories.
     *
     * @return writable {@link OutputStream}, or {@code null} on failure
     */
    public static OutputStream openOutputStreamByAbsPath(String absolutePath) {
        if (sContext == null || absolutePath == null) return null;
        try {
            DocumentFile newFile = createDocumentFile(absolutePath);
            if (newFile == null) return null;
            return sContext.getContentResolver().openOutputStream(newFile.getUri(), "w");
        } catch (Exception e) {
            Log.e(TAG, "openOutputStreamByAbsPath: " + e.getMessage());
            return null;
        }
    }

    /**
     * Resolves the parent directory via SAF, deletes any pre-existing file with the same name,
     * and creates a new {@link DocumentFile} ready for writing.
     *
     * @return the new {@link DocumentFile}, or {@code null} on any failure
     */
    private static DocumentFile createDocumentFile(String absolutePath) {
        File target = new File(absolutePath);
        String fileName = target.getName();
        String parentAbs = target.getParent();
        if (parentAbs == null) return null;

        String storageRoot = Environment.getExternalStorageDirectory().getAbsolutePath();
        if (!parentAbs.startsWith(storageRoot)) return null;
        String relativeParent = parentAbs.substring(storageRoot.length()).replaceAll("^/+", "");

        DocumentFile parentDir = DocumentFileCompat.fromSimplePath(
                sContext, StorageId.PRIMARY, relativeParent, DocumentFileType.FOLDER, true);
        if (parentDir == null || !parentDir.exists()) {
            Log.e(TAG, "createDocumentFile: folder not found via SAF: " + relativeParent);
            return null;
        }

        DocumentFile existing = parentDir.findFile(fileName);
        if (existing != null) existing.delete();

        DocumentFile newFile = parentDir.createFile(guessMime(fileName), fileName);
        if (newFile == null)
            Log.e(TAG, "createDocumentFile: createFile failed for " + fileName);
        return newFile;
    }

    private static String guessMime(String fileName) {
        String lower = fileName.toLowerCase();
        if (lower.endsWith(".flac"))             return "audio/flac";
        if (lower.endsWith(".png"))              return "image/png";
        if (lower.endsWith(".jpg")
                || lower.endsWith(".jpeg"))      return "image/jpeg";
        if (lower.endsWith(".csv")
                || lower.endsWith(".gcsv"))      return "text/csv";
        if (lower.endsWith(".txt"))              return "text/plain";
        if (lower.endsWith(".json"))             return "application/json";
        return "application/octet-stream";
    }
}
