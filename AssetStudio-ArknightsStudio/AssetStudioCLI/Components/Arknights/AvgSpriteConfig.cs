using AssetStudio;

namespace Arknights.AvgCharHubMono
{
    internal class AvgAssetIDs
    {
        public int m_FileID { get; set; }
        public long m_PathID { get; set; }
    }

    internal class AvgSpriteData
    {
        public AvgAssetIDs Sprite { get; set; }
        public AvgAssetIDs AlphaTex { get; set; }
        public string Alias { get; set; }
        public bool IsWholeBody { get; set; }
    }

    internal class AvgSpriteConfig
    {
        public AvgSpriteData[] Sprites { get; set; }
        public Vector2 FaceSize { get; set; }
        public Vector3 FacePos { get; set; }
    }

    internal class AvgSpriteConfigGroup
    {
        public AvgSpriteConfig[] SpriteGroups { get; set; }
    }
}
