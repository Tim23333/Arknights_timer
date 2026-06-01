namespace AssetStudioCLI.Options
{
    internal class Option<T>
    {
        public string Name { get; }
        public string Description { get; }
        public T Value { get; set; }
        public T DefaultValue { get; }
        public HelpGroups HelpGroup { get; }
        public bool IsFlag { get; }

        public Option(T optionDefaultValue, string optionName, string optionDescription, HelpGroups optionHelpGroup, bool isFlag)
        {
            Name = optionName;
            Description = optionDescription;
            DefaultValue = optionDefaultValue;
            Value = DefaultValue;
            HelpGroup = optionHelpGroup;
            IsFlag = isFlag;
        }

        public override string ToString()
        {
            return Value != null ? Value.ToString() : string.Empty;
        }
    }
}
