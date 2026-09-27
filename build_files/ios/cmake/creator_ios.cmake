# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

# iOS app-bundle policy invoked through the generic hooks in source/creator.

set(OSX_APP_SOURCEDIR "${CMAKE_SOURCE_DIR}/release/ios/Blender.app")
add_definitions(
  -DBLENDER_PLATFORM_MAIN=GHOST_iosmain
  -DBLENDER_PLATFORM_MAIN_CALLBACK=main_ios_callback
  -DBLENDER_PLATFORM_FINALIZE=GHOST_iosfinalize
)

macro(blender_platform_set_resource_directories)
  set(TARGETDIR_VER "Blender.app/Assets/${BLENDER_VERSION}")
  set(TARGETDIR_LIB "Blender.app/Assets/lib")
  set(TARGETDIR_TEXT "Blender.app/Assets/text")
endmacro()

macro(blender_platform_install_gltf_bridges addon_directory)
  install(CODE "
    execute_process(
      COMMAND \"${PYTHON_EXECUTABLE}\"
        \"${CMAKE_SOURCE_DIR}/build_files/ios/package_gltf_bridges.py\"
        --app-bundle \"\${CMAKE_INSTALL_PREFIX}/Blender.app\"
        --addon-directory \"\${CMAKE_INSTALL_PREFIX}/${addon_directory}\"
      COMMAND_ERROR_IS_FATAL ANY
    )
  ")
endmacro()

macro(blender_platform_configure_bundle target_name build_date)
  set_target_properties(${target_name} PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${OSX_APP_SOURCEDIR}/Info.plist"
    MACOSX_BUNDLE_SHORT_VERSION_STRING "${BLENDER_VERSION}.${BLENDER_VERSION_PATCH}"
    MACOSX_BUNDLE_LONG_VERSION_STRING
      "${BLENDER_VERSION}.${BLENDER_VERSION_PATCH} ${build_date}"
    XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY "1,2"
  )
endmacro()

macro(blender_platform_install_bundle_resources)
  install(
    FILES "${OSX_APP_SOURCEDIR}/PkgInfo"
    DESTINATION "Blender.app"
  )
  if(APPLE_TARGET_DEVICE STREQUAL "ios-simulator")
    set(_ios_asset_platform "iphonesimulator")
  else()
    set(_ios_asset_platform "iphoneos")
  endif()
  install(CODE "
    execute_process(
      COMMAND \"${PYTHON_EXECUTABLE}\"
        \"${CMAKE_SOURCE_DIR}/build_files/ios/compile_asset_catalog.py\"
        --app-bundle \"\${CMAKE_INSTALL_PREFIX}/Blender.app\"
        --icon-package \"${CMAKE_SOURCE_DIR}/release/ios/modeling3d.icon\"
        --platform \"${_ios_asset_platform}\"
        --minimum-os \"${CMAKE_OSX_DEPLOYMENT_TARGET}\"
      COMMAND_ERROR_IS_FATAL ANY
    )
  ")
  unset(_ios_asset_platform)
endmacro()

macro(blender_platform_install_python)
  set(BLENDER_PLATFORM_PYTHON_INSTALLED ON)
  install(
    DIRECTORY "${LIBDIR}/python/Python.framework"
    DESTINATION "Blender.app/Frameworks"
    PATTERN "Headers" EXCLUDE
  )
  install_dir(
    "${PYTHON_LIBPATH}/python${PYTHON_VERSION}"
    "${TARGETDIR_VER}/python/lib"
  )

  if(APPLE_TARGET_DEVICE STREQUAL "ios-simulator")
    set(_python_ios_platform "iPhoneSimulator")
  else()
    set(_python_ios_platform "iPhoneOS")
  endif()
  install(CODE "
    execute_process(
      COMMAND \"${PYTHON_EXECUTABLE}\"
        \"${CMAKE_SOURCE_DIR}/build_files/ios/package_python_frameworks.py\"
        --app-bundle \"\${CMAKE_INSTALL_PREFIX}/Blender.app\"
        --import-root
          \"\${CMAKE_INSTALL_PREFIX}/${TARGETDIR_VER}/python/lib/python${PYTHON_VERSION}\"
        --bundle-identifier \"com.shlokbhakta.modeling3d\"
        --platform \"${_python_ios_platform}\"
        --minimum-os \"${CMAKE_OSX_DEPLOYMENT_TARGET}\"
      COMMAND_ERROR_IS_FATAL ANY
    )
  ")
  unset(_python_ios_platform)
endmacro()
