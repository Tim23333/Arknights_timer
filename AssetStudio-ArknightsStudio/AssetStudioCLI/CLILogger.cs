using AssetStudio;
using AssetStudioCLI.Options;
using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace AssetStudioCLI
{
    internal enum LogOutputMode
    {
        Console,
        File,
        Both,
    }

    internal class CLILogger : ILogger
    {
        private readonly LogOutputMode logOutput;
        private readonly LoggerEvent logMinLevel;
        public string LogName;
        public string LogPath;

        public CLILogger()
        {
            logOutput = CLIOptions.o_logOutput.Value;
            logMinLevel = CLIOptions.o_logLevel.Value;
            var appAssembly = typeof(Program).Assembly.GetName();
            LogName = $"{appAssembly.Name}_{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.log";
            LogPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, LogName);
            var arch = Environment.Is64BitProcess ? "x64" : "x32";
            Console.OutputEncoding = System.Text.Encoding.UTF8;

            LogToFile(LoggerEvent.Verbose, $"---{appAssembly.Name} v{appAssembly.Version} [{arch}] | Logger launched---\n" +
                                           $"CMD Args: {string.Join(" ", CLIOptions.cliArgs)}");
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

        private static string FormatMessage(LoggerEvent logMsgLevel, string message, bool consoleMode = false)
        {
            var curTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            message = message.TrimEnd();
            var multiLine = message.Contains('\n');
            
            string formattedMessage;
            if (consoleMode)
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

        public void LogToConsole(LoggerEvent logMsgLevel, string message)
        {
            if (logOutput != LogOutputMode.File)
            {
                Console.WriteLine(FormatMessage(logMsgLevel, message, consoleMode: true));
            }
        }

        public async void LogToFile(LoggerEvent logMsgLevel, string message)
        {
            if (logOutput != LogOutputMode.Console)
            {
                using (var sw = new StreamWriter(LogPath, append: true, System.Text.Encoding.UTF8))
                {
                    await sw.WriteLineAsync(FormatMessage(logMsgLevel, message));
                }
            }
        }

        public void Log(LoggerEvent logMsgLevel, string message, bool ignoreLevel)
        {
            if ((logMsgLevel < logMinLevel && !ignoreLevel) || string.IsNullOrEmpty(message))
            {
                return;
            }

            if (logOutput != LogOutputMode.File)
            {
                LogToConsole(logMsgLevel, message);
            }
            if (logOutput != LogOutputMode.Console)
            {
                LogToFile(logMsgLevel, message);
            }
        }
    }
}
