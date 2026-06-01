using AssetStudio;
using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace AssetStudioGUI
{
    class GUILogger : ILogger
    {
        public bool ShowErrorMessage = false;
        private bool IsFileLoggerRunning = false;
        private string LoggerInitString;
        private string FileLogName;
        private string FileLogPath;
        private Action<string> action;

        private bool _useFileLogger = false;
        public bool UseFileLogger
        {
            get => _useFileLogger;
            set
            {
                _useFileLogger = value;
                if (_useFileLogger && !IsFileLoggerRunning)
                {
                    var appAssembly = typeof(Program).Assembly.GetName();
                    FileLogName = $"{appAssembly.Name}_{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.log";
                    FileLogPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, FileLogName);

                    LogToFile(LoggerEvent.Verbose, $"# {LoggerInitString} - Logger launched #");
                    IsFileLoggerRunning = true;
                }
                else if (!_useFileLogger && IsFileLoggerRunning)
                {
                    LogToFile(LoggerEvent.Verbose, "# Logger closed #");
                    IsFileLoggerRunning = false;
                }
            }
        }

        public GUILogger(Action<string> action)
        {
            this.action = action;

            var appAssembly = typeof(Program).Assembly.GetName();
            var arch = Environment.Is64BitProcess ? "x64" : "x32";
            var frameworkName = AppDomain.CurrentDomain.SetupInformation.TargetFrameworkName;
            LoggerInitString = $"{appAssembly.Name} v{appAssembly.Version} [{arch}] [{frameworkName}]";
            try
            {
                Console.Title = $"Console Logger - {appAssembly.Name} v{appAssembly.Version}";
                Console.OutputEncoding = System.Text.Encoding.UTF8;
            }
            catch
            {
                // ignored
            }
            Console.WriteLine($"# {LoggerInitString}");
        }

        private static string ColorLogLevel(LoggerEvent logLevel)
        {
            var formattedLevel = $"[{logLevel}]";
            switch (logLevel)
            {
                case LoggerEvent.Info:
                    return $"{formattedLevel.Color(ColorConsole.BrightCyan)}";
                case LoggerEvent.Warning:
                    return $"{formattedLevel.Color(ColorConsole.BrightYellow)}";
                case LoggerEvent.Error:
                    return $"{formattedLevel.Color(ColorConsole.BrightRed)}";
                default:
                    return formattedLevel;
            }
        }

        private static string FormatMessage(LoggerEvent logMsgLevel, string message, bool toConsole)
        {
            message = message.TrimEnd();
            var multiLine = message.Contains('\n');

            string formattedMessage;
            if (toConsole)
            {
                var colorLogLevel = ColorLogLevel(logMsgLevel);
                formattedMessage = $"{colorLogLevel} {message}";
                if (multiLine)
                {
                    formattedMessage = formattedMessage.Replace("\n", $"\n{colorLogLevel} ");
                }
            }
            else
            {
                var curTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
                message = Regex.Replace(message, @"\e\[[0-9;]*m(?:\e\[K)?", "");  //Delete ANSI colors
                var logLevel = $"{logMsgLevel.ToString().ToUpper(),-7}";
                formattedMessage = $"{curTime} | {logLevel} | {message}";
                if (multiLine)
                {
                    formattedMessage = formattedMessage.Replace("\n", $"\n{curTime} | {logLevel} | ");
                }
            }

            return formattedMessage;
        }

        private async void LogToFile(LoggerEvent logMsgLevel, string message)
        {
            using (var sw = new StreamWriter(FileLogPath, append: true, System.Text.Encoding.UTF8))
            {
                await sw.WriteLineAsync(FormatMessage(logMsgLevel, message, toConsole: false));
            }
        }

        public void Log(LoggerEvent loggerEvent, string message, bool ignoreLevel)
        {
            //File logger
            if (_useFileLogger)
            {
                LogToFile(loggerEvent, message);
            }

            //Console logger
            Console.WriteLine(FormatMessage(loggerEvent, message, toConsole: true));

            //GUI logger
            switch (loggerEvent)
            {
                case LoggerEvent.Error:
                    MessageBox.Show(message, "Error");
                    break;
                case LoggerEvent.Warning:
                    if (ShowErrorMessage)
                    {
                        MessageBox.Show(message, "Warning");
                    }
                    else
                    {
                        action("An error has occurred. Turn on \"Show all error messages\" to see details next time.");
                    }
                    break;
                case LoggerEvent.Debug:
                    break;
                default:
                    action(message);
                    break;
            }
        }
    }
}
