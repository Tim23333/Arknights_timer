using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

#if NETFRAMEWORK
namespace AssetStudio.PInvoke
{
    public static class DllLoader
    {
        public static void PreloadDll(string dllName)
        {
            var localPath = Process.GetCurrentProcess().MainModule.FileName;
            var localDir = Path.GetDirectoryName(localPath);

            // Not using OperatingSystem.Platform.
            // See: https://www.mono-project.com/docs/faq/technical/#how-to-detect-the-execution-platform
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                Win32.LoadDll(GetDirectedDllDirectory(localDir), dllName);
            }
        }

        private static string GetDirectedDllDirectory(string localDir)
        {
            var win32Path = Path.Combine("runtimes", "win-x86", "native");
            var win64Path = Path.Combine("runtimes", "win-x64", "native");
            var subDir = Environment.Is64BitProcess ? win64Path : win32Path;

            var directedDllDir = Path.Combine(localDir, subDir);

            return directedDllDir;
        }

        private static class Win32
        {

            internal static void LoadDll(string dllDir, string dllName)
            {
                var dllFileName = $"{dllName}.dll";
                var directedDllPath = Path.Combine(dllDir, dllFileName);

                // Specify SEARCH_DLL_LOAD_DIR to load dependent libraries located in the same platform-specific directory.
                var hLibrary = LoadLibraryEx(directedDllPath, IntPtr.Zero, LOAD_LIBRARY_SEARCH_DEFAULT_DIRS | LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR);

                if (hLibrary == IntPtr.Zero)
                {
                    var errorCode = Marshal.GetLastWin32Error();
                    var exception = new Win32Exception(errorCode);

                    throw new DllNotFoundException(exception.Message, exception);
                }
            }

            // HMODULE LoadLibraryExA(LPCSTR lpLibFileName, HANDLE hFile, DWORD dwFlags);
            // HMODULE LoadLibraryExW(LPCWSTR lpLibFileName, HANDLE hFile, DWORD dwFlags);
            [DllImport("kernel32.dll", SetLastError = true)]
            private static extern IntPtr LoadLibraryEx(string lpLibFileName, IntPtr hFile, uint dwFlags);

            private const uint LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x1000;
            private const uint LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x100;
        }
    }
}
#endif
