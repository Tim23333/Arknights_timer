using System;

namespace AssetStudioCLI.Options
{
    internal static class OptionExtensions
    {
        public static Action<string, string, HelpGroups, bool> OptionGrouping = (name, desc, group, isFlag) => { };
    }

    internal class GroupedOption<T> : Option<T>
    {
        public GroupedOption(T optionDefaultValue, string optionName, string optionDescription, HelpGroups optionHelpGroup, bool isFlag = false) : base(optionDefaultValue, optionName, optionDescription, optionHelpGroup, isFlag)
        {
            OptionExtensions.OptionGrouping(optionName, optionDescription, optionHelpGroup, isFlag);
        }
    }
}
