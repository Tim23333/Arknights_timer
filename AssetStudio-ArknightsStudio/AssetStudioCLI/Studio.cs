using AssetStudio;
using AssetStudioCLI.Options;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Xml.Linq;
using static AssetStudioCLI.Exporter;
using static CubismLive2DExtractor.Live2DExtractor;
using Ansi = AssetStudio.ColorConsole;

namespace AssetStudioCLI
{
    internal static class Studio
    {
        public static AssetsManager assetsManager = new AssetsManager();
        public static List<AssetItem> exportableAssetsList = new List<AssetItem>();
        public static List<AssetItem> loadedAssetsList = new List<AssetItem>();
        public static List<BaseNode> gameObjectTree = new List<BaseNode>();
        public static AssemblyLoader assemblyLoader = new AssemblyLoader();
        private static Dictionary<AssetStudio.Object, string> containers = new Dictionary<AssetStudio.Object, string>();

        static Studio()
        {
            Progress.Default = new Progress<int>(ShowCurProgressValue);
        }

        private static void ShowCurProgressValue(int value)
        {
            Console.Write($"[{value:000}%]\r");
        }

        public static bool LoadAssets()
        {
            var isLoaded = false;
            assetsManager.SpecifyUnityVersion = CLIOptions.o_unityVersion.Value;
            if (!CLIOptions.f_loadAllAssets.Value)
            {
                assetsManager.SetAssetFilter(CLIOptions.o_exportAssetTypes.Value);
            }
            assetsManager.LoadFilesAndFolders(CLIOptions.inputPath);
            if (assetsManager.assetsFileList.Count == 0)
            {
                Logger.Warning("No Unity file can be loaded.");
            }
            else
            {
                isLoaded = true;
            }

            return isLoaded;
        }

        public static void ParseAssets()
        {
            Logger.Info("Parse assets...");

            var objectCount = assetsManager.assetsFileList.Sum(x => x.Objects.Count);
            var objectAssetItemDic = new Dictionary<AssetStudio.Object, AssetItem>(objectCount);

            Progress.Reset();
            var i = 0;
            foreach (var assetsFile in assetsManager.assetsFileList)
            {
                var preloadTable = Array.Empty<PPtr<AssetStudio.Object>>();
                foreach (var asset in assetsFile.Objects)
                {
                    var assetItem = new AssetItem(asset);
                    objectAssetItemDic.Add(asset, assetItem);
                    assetItem.UniqueID = "_#" + i;
                    var isExportable = false;
                    switch (asset)
                    {
                        case PreloadData m_PreloadData:
                            preloadTable = m_PreloadData.m_Assets;
                            break;
                        case AssetBundle m_AssetBundle:
                            var isStreamedSceneAssetBundle = m_AssetBundle.m_IsStreamedSceneAssetBundle;
                            if (!isStreamedSceneAssetBundle)
                            {
                                preloadTable = m_AssetBundle.m_PreloadTable;
                            }
                            assetItem.Text = string.IsNullOrEmpty(m_AssetBundle.m_AssetBundleName) ? m_AssetBundle.m_Name : m_AssetBundle.m_AssetBundleName;

                            foreach (var m_Container in m_AssetBundle.m_Container)
                            {
                                var preloadIndex = m_Container.Value.preloadIndex;
                                var preloadSize = isStreamedSceneAssetBundle ? preloadTable.Length : m_Container.Value.preloadSize;
                                var preloadEnd = preloadIndex + preloadSize;
                                for (var k = preloadIndex; k < preloadEnd; k++)
                                {
                                    var pptr = preloadTable[k];
                                    if (pptr.TryGet(out var obj))
                                    {
                                        containers[obj] = m_Container.Key;
                                    }
                                }
                            }
                            break;
                        case ResourceManager m_ResourceManager:
                            foreach (var m_Container in m_ResourceManager.m_Container)
                            {
                                if (m_Container.Value.TryGet(out var obj))
                                {
                                    containers[obj] = m_Container.Key;
                                }
                            }
                            break;
                        case Texture2D m_Texture2D:
                            if (!string.IsNullOrEmpty(m_Texture2D.m_StreamData?.path))
                                assetItem.FullSize = asset.byteSize + m_Texture2D.m_StreamData.size;
                            assetItem.Text = m_Texture2D.m_Name;
                            break;
                        case AudioClip m_AudioClip:
                            if (!string.IsNullOrEmpty(m_AudioClip.m_Source))
                                assetItem.FullSize = asset.byteSize + m_AudioClip.m_Size;
                            assetItem.Text = m_AudioClip.m_Name;
                            break;
                        case VideoClip m_VideoClip:
                            if (!string.IsNullOrEmpty(m_VideoClip.m_OriginalPath))
                                assetItem.FullSize = asset.byteSize + m_VideoClip.m_ExternalResources.m_Size;
                            assetItem.Text = m_VideoClip.m_Name;
                            break;
                        case Shader m_Shader:
                            assetItem.Text = m_Shader.m_ParsedForm?.m_Name ?? m_Shader.m_Name;
                            break;
                        case MonoBehaviour m_MonoBehaviour:
                            if (m_MonoBehaviour.m_Name == "" && m_MonoBehaviour.m_Script.TryGet(out var m_Script))
                            {
                                assetItem.Text = m_Script.m_ClassName;
                            }
                            else
                            {
                                assetItem.Text = m_MonoBehaviour.m_Name;
                            }
                            break;
                        case GameObject m_GameObject:
                            assetItem.Text = m_GameObject.m_Name;
                            break;
                        case Animator m_Animator:
                            if (m_Animator.m_GameObject.TryGet(out var gameObject))
                            {
                                assetItem.Text = gameObject.m_Name;
                            }
                            break;
                        case NamedObject m_NamedObject:
                            assetItem.Text = m_NamedObject.m_Name;
                            break;
                    }
                    if (string.IsNullOrEmpty(assetItem.Text))
                    {
                        assetItem.Text = assetItem.TypeString + assetItem.UniqueID;
                    }

                    loadedAssetsList.Add(assetItem);
                    isExportable = CLIOptions.o_exportAssetTypes.Value.Contains(asset.type);
                    if (isExportable || (CLIOptions.f_loadAllAssets.Value && CLIOptions.o_exportAssetTypes.Value == CLIOptions.o_exportAssetTypes.DefaultValue))
                    {
                        exportableAssetsList.Add(assetItem);
                    }

                    Progress.Report(++i, objectCount);
                }
                foreach (var asset in loadedAssetsList)
                {
                    if (containers.TryGetValue(asset.Asset, out var container))
                    {
                        asset.Container = container;

                        if (asset.Type == ClassIDType.MonoBehaviour && container.Contains("/arts/charportraits/portraits"))
                        {
                            var portraitsList = Arknights.AkSpriteHelper.GeneratePortraits(asset);
                            foreach (var portrait in portraitsList)
                            {
                                exportableAssetsList.Add(new AssetItem(portrait));
                            }
                        }
                    }
                }
                if (CLIOptions.o_workMode.Value != WorkMode.ExportLive2D)
                {
                    containers.Clear();
                }
            }

            if (CLIOptions.o_workMode.Value == WorkMode.SplitObjects)
            {
                BuildTreeStructure(objectAssetItemDic);
            }
            var log = $"Finished loading {assetsManager.assetsFileList.Count} files with {exportableAssetsList.Count} exportable assets";
            var unityVer = assetsManager.assetsFileList[0].version;
            long m_ObjectsCount;
            if (unityVer[0] > 2020)
            {
                m_ObjectsCount = assetsManager.assetsFileList.Sum(x => x.m_Objects.LongCount(y =>
                    y.classID != (int)ClassIDType.Shader
                    && CLIOptions.o_exportAssetTypes.Value.Any(k => (int)k == y.classID))
                );
            }
            else
            {
                m_ObjectsCount = assetsManager.assetsFileList.Sum(x => x.m_Objects.LongCount(y => CLIOptions.o_exportAssetTypes.Value.Any(k => (int)k == y.classID)));
            }
            var objectsCount = assetsManager.assetsFileList.Sum(x => x.Objects.LongCount(y => CLIOptions.o_exportAssetTypes.Value.Any(k => k == y.type)));
            if (m_ObjectsCount != objectsCount)
            {
                log += $" and {m_ObjectsCount - objectsCount} assets failed to read";
            }
            Logger.Info(log);
        }

        public static void BuildTreeStructure(Dictionary<AssetStudio.Object, AssetItem> objectAssetItemDic)
        {
            Logger.Info("Building tree structure...");

            var treeNodeDictionary = new Dictionary<GameObject, GameObjectNode>();
            var assetsFileCount = assetsManager.assetsFileList.Count;
            int j = 0;
            Progress.Reset();
            foreach (var assetsFile in assetsManager.assetsFileList)
            {
                var fileNode = new BaseNode();  //RootNode

                foreach (var obj in assetsFile.Objects)
                {
                    if (obj is GameObject m_GameObject)
                    {
                        if (!treeNodeDictionary.TryGetValue(m_GameObject, out var currentNode))
                        {
                            currentNode = new GameObjectNode(m_GameObject);
                            treeNodeDictionary.Add(m_GameObject, currentNode);
                        }
                        
                        foreach (var pptr in m_GameObject.m_Components)
                        {
                            if (pptr.TryGet(out var m_Component))
                            {
                                objectAssetItemDic[m_Component].Node = currentNode;
                                if (m_Component is MeshFilter m_MeshFilter)
                                {
                                    if (m_MeshFilter.m_Mesh.TryGet(out var m_Mesh))
                                    {
                                        objectAssetItemDic[m_Mesh].Node = currentNode;
                                    }
                                }
                                else if (m_Component is SkinnedMeshRenderer m_SkinnedMeshRenderer)
                                {
                                    if (m_SkinnedMeshRenderer.m_Mesh.TryGet(out var m_Mesh))
                                    {
                                        objectAssetItemDic[m_Mesh].Node = currentNode;
                                    }
                                }
                            }
                        }

                        var parentNode = fileNode;

                        if (m_GameObject.m_Transform != null)
                        {
                            if (m_GameObject.m_Transform.m_Father.TryGet(out var m_Father))
                            {
                                if (m_Father.m_GameObject.TryGet(out var parentGameObject))
                                {
                                    if (!treeNodeDictionary.TryGetValue(parentGameObject, out var parentGameObjectNode))
                                    {
                                        parentGameObjectNode = new GameObjectNode(parentGameObject);
                                        treeNodeDictionary.Add(parentGameObject, parentGameObjectNode);
                                    }
                                    parentNode = parentGameObjectNode;
                                }
                            }
                        }

                        parentNode.nodes.Add(currentNode);

                    }
                }

                if (fileNode.nodes.Count > 0)
                {
                    gameObjectTree.Add(fileNode);
                }

                Progress.Report(++j, assetsFileCount);
            }

            treeNodeDictionary.Clear();
            objectAssetItemDic.Clear();
        }

        public static void ShowExportableAssetsInfo()
        {
            var exportableAssetsCountDict = new Dictionary<ClassIDType, int>();
            string info = "";
            if (exportableAssetsList.Count > 0)
            {
                foreach (var asset in exportableAssetsList)
                {
                    if (exportableAssetsCountDict.ContainsKey(asset.Type))
                    {
                        exportableAssetsCountDict[asset.Type] += 1;
                    }
                    else
                    {
                        exportableAssetsCountDict.Add(asset.Type, 1);
                    }
                }

                info += "\n[Exportable Assets Count]\n";
                foreach (var assetType in exportableAssetsCountDict.Keys)
                {
                    info += $"# {assetType}: {exportableAssetsCountDict[assetType]}\n";
                }
                if (exportableAssetsCountDict.Count > 1)
                {
                    info += $"#\n# Total: {exportableAssetsList.Count} assets";
                }
            }
            else
            {
                info += "No exportable assets found.";
            }

            if (CLIOptions.o_logLevel.Value > LoggerEvent.Info)
            {
                Console.WriteLine(info);
            }
            else
            {
                Logger.Info(info);
            }
        }

        public static void Filter()
        {
            switch (CLIOptions.o_workMode.Value)
            {
                case WorkMode.ExportLive2D:
                case WorkMode.SplitObjects:
                    break;
                default:
                    FilterAssets();
                    break;
            }
        }

        private static void FilterAssets()
        {
            var assetsCount = exportableAssetsList.Count;
            var filteredAssets = new List<AssetItem>();

            switch(CLIOptions.filterBy)
            {
                case FilterBy.Name:
                    filteredAssets = exportableAssetsList.FindAll(x => CLIOptions.o_filterByName.Value.Any(y => x.Text.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0));
                    Logger.Info(
                        $"Found [{filteredAssets.Count}/{assetsCount}] asset(s) " +
                        $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByName.Value)}\"".Color(Ansi.BrightYellow)} in their Names."
                    );
                    break;
                case FilterBy.Container:
                    filteredAssets = exportableAssetsList.FindAll(x => CLIOptions.o_filterByContainer.Value.Any(y => x.Container.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0));
                    Logger.Info(
                        $"Found [{filteredAssets.Count}/{assetsCount}] asset(s) " +
                        $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByContainer.Value)}\"".Color(Ansi.BrightYellow)} in their Containers."
                    );
                    break;
                case FilterBy.PathID:
                    filteredAssets = exportableAssetsList.FindAll(x => CLIOptions.o_filterByPathID.Value.Any(y => x.m_PathID.ToString().IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0));
                    Logger.Info(
                        $"Found [{filteredAssets.Count}/{assetsCount}] asset(s) " +
                        $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByPathID.Value)}\"".Color(Ansi.BrightYellow)} in their PathIDs."
                    );
                    break;
                case FilterBy.NameOrContainer:
                    filteredAssets = exportableAssetsList.FindAll(x =>
                        CLIOptions.o_filterByText.Value.Any(y => x.Text.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0) ||
                        CLIOptions.o_filterByText.Value.Any(y => x.Container.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0)
                    );
                    Logger.Info(
                        $"Found [{filteredAssets.Count}/{assetsCount}] asset(s) " +
                        $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByText.Value)}\"".Color(Ansi.BrightYellow)} in their Names or Contaniers."
                    );
                    break;
                case FilterBy.NameAndContainer:
                    filteredAssets = exportableAssetsList.FindAll(x =>
                        CLIOptions.o_filterByName.Value.Any(y => x.Text.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0) &&
                        CLIOptions.o_filterByContainer.Value.Any(y => x.Container.IndexOf(y, StringComparison.OrdinalIgnoreCase) >= 0)
                    );
                    Logger.Info(
                        $"Found [{filteredAssets.Count}/{assetsCount}] asset(s) " +
                        $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByContainer.Value)}\"".Color(Ansi.BrightYellow)} in their Containers " +
                        $"and {$"\"{string.Join("\", \"", CLIOptions.o_filterByName.Value)}\"".Color(Ansi.BrightYellow)} in their Names."
                    );
                    break;
            }
            exportableAssetsList.Clear();
            exportableAssetsList = filteredAssets;
        }

        public static void ExportAssets()
        {
            var savePath = CLIOptions.o_outputFolder.Value;
            var toExportCount = exportableAssetsList.Count;
            var exportedCount = 0;

            var groupOption = CLIOptions.o_groupAssetsBy.Value;
            foreach (var asset in exportableAssetsList)
            {
                string exportPath;
                switch (groupOption)
                {
                    case AssetGroupOption.TypeName:
                        exportPath = Path.Combine(savePath, asset.TypeString);
                        break;
                    case AssetGroupOption.ContainerPath:
                    case AssetGroupOption.ContainerPathFull:
                        if (!string.IsNullOrEmpty(asset.Container))
                        {
                            exportPath = Path.Combine(savePath, Path.GetDirectoryName(asset.Container));
                            if (groupOption == AssetGroupOption.ContainerPathFull)
                            {
                                exportPath = Path.Combine(exportPath, Path.GetFileNameWithoutExtension(asset.Container));
                            }
                        }
                        else
                        {
                            exportPath = savePath;
                        }
                        break;
                    case AssetGroupOption.SourceFileName:
                        if (string.IsNullOrEmpty(asset.SourceFile.originalPath))
                        {
                            exportPath = Path.Combine(savePath, asset.SourceFile.fileName + "_export");
                        }
                        else
                        {
                            exportPath = Path.Combine(savePath, Path.GetFileName(asset.SourceFile.originalPath) + "_export", asset.SourceFile.fileName);
                        }
                        break;
                    default:
                        exportPath = savePath;
                        break;
                }

                exportPath += Path.DirectorySeparatorChar;
                try
                {
                    switch (CLIOptions.o_workMode.Value)
                    {
                        case WorkMode.ExportRaw:
                            Logger.Debug($"{CLIOptions.o_workMode}: {asset.Type} : {asset.Container} : {asset.Text}");
                            if (ExportRawFile(asset, exportPath))
                            {
                                exportedCount++;
                            }
                            break;
                        case WorkMode.Dump:
                            Logger.Debug($"{CLIOptions.o_workMode}: {asset.Type} : {asset.Container} : {asset.Text}");
                            if (ExportDumpFile(asset, exportPath))
                            {
                                exportedCount++;
                            }
                            break;
                        case WorkMode.Export:
                            Logger.Debug($"{CLIOptions.o_workMode}: {asset.Type} : {asset.Container} : {asset.Text}");
                            if (ExportConvertFile(asset, exportPath))
                            {
                                exportedCount++;
                            }
                            break;
                    }
                }
                catch (Exception ex)
                {
                    Logger.Error($"{asset.SourceFile.originalPath}: [{$"{asset.Type}: {asset.Text}".Color(Ansi.BrightRed)}] : Export error\n{ex}");
                }
                Console.Write($"Exported [{exportedCount}/{toExportCount}]\r");
            }
            Console.WriteLine("");

            if (exportedCount == 0)
            {
                Logger.Default.Log(LoggerEvent.Info, "Nothing exported.", ignoreLevel: true);
            }
            else if (toExportCount > exportedCount)
            {
                Logger.Default.Log(LoggerEvent.Info, $"Finished exporting {exportedCount} asset(s) to \"{CLIOptions.o_outputFolder.Value.Color(Ansi.BrightYellow)}\".", ignoreLevel: true);
            }
            else
            {
                Logger.Default.Log(LoggerEvent.Info, $"Finished exporting {exportedCount} asset(s) to \"{CLIOptions.o_outputFolder.Value.Color(Ansi.BrightGreen)}\".", ignoreLevel: true);
            }

            if (toExportCount > exportedCount)
            {
                Logger.Default.Log(LoggerEvent.Info, $"{toExportCount - exportedCount} asset(s) skipped (not extractable or file(s) already exist).", ignoreLevel: true);
            }
        }

        public static void ExportAssetList()
        {
            var savePath = CLIOptions.o_outputFolder.Value;

            switch (CLIOptions.o_exportAssetList.Value)
            {
                case ExportListType.XML:
                    var filename = Path.Combine(savePath, "assets.xml");
                    var doc = new XDocument(
                        new XElement("Assets",
                            new XAttribute("filename", filename),
                            new XAttribute("createdAt", DateTime.UtcNow.ToString("s")),
                            exportableAssetsList.Select(
                                asset => new XElement("Asset",
                                    new XElement("Name", asset.Text),
                                    new XElement("Container", asset.Container),
                                    new XElement("Type", new XAttribute("id", (int)asset.Type), asset.TypeString),
                                    new XElement("PathID", asset.m_PathID),
                                    new XElement("Source", asset.SourceFile.fullName),
                                    new XElement("Size", asset.FullSize)
                                )
                            )
                        )
                    );
                    doc.Save(filename);

                   break;
            }
            Logger.Info($"Finished exporting asset list with {exportableAssetsList.Count} items.");
        }

        public static void ExportSplitObjects()
        {
            var savePath = CLIOptions.o_outputFolder.Value;
            var searchList = CLIOptions.o_filterByName.Value;
            var isFiltered = CLIOptions.filterBy == FilterBy.Name;

            var exportableObjects = new List<GameObjectNode>();
            var exportedCount = 0;
            var k = 0;

            Logger.Info($"Searching for objects to export..");
            Progress.Reset();
            var count = gameObjectTree.Sum(x => x.nodes.Count);
            foreach (var node in gameObjectTree)
            {
                foreach (GameObjectNode j in node.nodes)
                {
                    if (isFiltered)
                    {
                        if (!searchList.Any(searchText => j.gameObject.m_Name.IndexOf(searchText, StringComparison.OrdinalIgnoreCase) >= 0))
                            continue;
                    }
                    var gameObjects = new List<GameObject>();
                    CollectNode(j, gameObjects);

                    if (gameObjects.All(x => x.m_SkinnedMeshRenderer == null && x.m_MeshFilter == null))
                    {
                        Progress.Report(++k, count);
                        continue;
                    }
                    exportableObjects.Add(j);
                }
            }
            gameObjectTree.Clear();
            var exportableCount = exportableObjects.Count;
            var log = $"Found {exportableCount} exportable object(s) ";
            if (isFiltered)
            {
                log += $"that contain {$"\"{string.Join("\", \"", CLIOptions.o_filterByName.Value)}\"".Color(Ansi.BrightYellow)} in their Names";
            }
            Logger.Info(log);
            if (exportableCount > 0)
            {
                Progress.Reset();
                k = 0;

                foreach (var gameObjectNode in exportableObjects)
                {
                    var gameObject = gameObjectNode.gameObject;
                    var filename = FixFileName(gameObject.m_Name);
                    var targetPath = $"{savePath}{filename}{Path.DirectorySeparatorChar}";
                    //重名文件处理
                    for (int i = 1; ; i++)
                    {
                        if (Directory.Exists(targetPath))
                        {
                            targetPath = $"{savePath}{filename} ({i}){Path.DirectorySeparatorChar}";
                        }
                        else
                        {
                            break;
                        }
                    }
                    Directory.CreateDirectory(targetPath);
                    //导出FBX
                    Logger.Info($"Exporting {filename}.fbx");
                    Progress.Report(k, exportableCount);
                    try
                    {
                        ExportGameObject(gameObject, targetPath);
                        Logger.Debug($"{gameObject.type} \"{filename}\" saved to \"{targetPath}\"");
                        exportedCount++;
                    }
                    catch (Exception ex)
                    {
                        Logger.Error($"Export GameObject:{gameObject.m_Name} error", ex);
                    }
                    k++;
                }
            }
            var status = exportedCount > 0
                ? $"Finished exporting [{exportedCount}/{exportableCount}] object(s) to \"{CLIOptions.o_outputFolder.Value.Color(Ansi.BrightCyan)}\""
                : "Nothing exported";
            Logger.Default.Log(LoggerEvent.Info, status, ignoreLevel: true);
        }

        private static void CollectNode(GameObjectNode node, List<GameObject> gameObjects)
        {
            gameObjects.Add(node.gameObject);
            foreach (GameObjectNode i in node.nodes)
            {
                CollectNode(i, gameObjects);
            }
        }

        public static void ExportLive2D()
        {
            var baseDestPath = Path.Combine(CLIOptions.o_outputFolder.Value, "Live2DOutput");
            var useFullContainerPath = false;
            var motionMode = CLIOptions.o_l2dMotionMode.Value;
            var forceBezier = CLIOptions.f_l2dForceBezier.Value;

            Progress.Reset();
            Logger.Info($"Searching for Live2D files...");

            var cubismMocs = exportableAssetsList.Where(x =>
            {
                if (x.Type == ClassIDType.MonoBehaviour)
                {
                    ((MonoBehaviour)x.Asset).m_Script.TryGet(out var m_Script);
                    return m_Script?.m_ClassName == "CubismMoc";
                }
                return false;
            }).Select(x => x.Asset).ToArray();

            if (cubismMocs.Length == 0)
            {
                Logger.Default.Log(LoggerEvent.Info, "Live2D Cubism models were not found.", ignoreLevel: true);
                return;
            }
            if (cubismMocs.Length > 1)
            {
                var basePathSet = cubismMocs.Select(x =>
                {
                    var pathLen = containers.TryGetValue(x, out var itemContainer) ? itemContainer.LastIndexOf("/") : 0;
                    pathLen = pathLen < 0 ? containers[x].Length : pathLen;
                    return itemContainer?.Substring(0, pathLen);
                }).ToHashSet();

                if (basePathSet.All(x => x == null))
                {
                    Logger.Error($"Live2D Cubism export error: Cannot find any model related files.");
                    return;
                }

                if (basePathSet.Count != cubismMocs.Length)
                {
                    useFullContainerPath = true;
                    Logger.Debug($"useFullContainerPath: {useFullContainerPath}");
                }
            }

            var basePathList = cubismMocs.Select(x =>
            {
                containers.TryGetValue(x, out var container);
                container = useFullContainerPath
                    ? container
                    : container?.Substring(0, container.LastIndexOf("/"));
                return container;
            }).Where(x => x != null).ToList();

            var lookup = containers.ToLookup(
                x => basePathList.Find(b => x.Value.Contains(b) && x.Value.Split('/').Any(y => y == b.Substring(b.LastIndexOf("/") + 1))),
                x => x.Key
            );

            var totalModelCount = lookup.LongCount(x => x.Key != null);
            Logger.Info($"Found {totalModelCount} model(s).");
            var modelCounter = 0;
            foreach (var assets in lookup)
            {
                var srcContainer = assets.Key;
                if (srcContainer == null)
                    continue;
                var container = srcContainer;

                Logger.Info($"[{modelCounter + 1}/{totalModelCount}] Exporting Live2D: \"{srcContainer.Color(Ansi.BrightCyan)}\"");
                try
                {
                    var modelName = useFullContainerPath ? Path.GetFileNameWithoutExtension(container) : container.Substring(container.LastIndexOf('/') + 1);
                    container = Path.HasExtension(container) ? container.Replace(Path.GetExtension(container), "") : container;
                    var destPath = Path.Combine(baseDestPath, container) + Path.DirectorySeparatorChar;

                    ExtractLive2D(assets, destPath, modelName, assemblyLoader, motionMode, forceBezier);
                    modelCounter++;
                }
                catch (Exception ex)
                {
                    Logger.Error($"Live2D model export error: \"{srcContainer}\"", ex);
                }
                Progress.Report(modelCounter, (int)totalModelCount);
            }

            var status = modelCounter > 0 ?
                $"Finished exporting [{modelCounter}/{totalModelCount}] Live2D model(s) to \"{CLIOptions.o_outputFolder.Value.Color(Ansi.BrightCyan)}\"" :
                "Nothing exported.";
            Logger.Default.Log(LoggerEvent.Info, status, ignoreLevel: true);
        }
    }
}
