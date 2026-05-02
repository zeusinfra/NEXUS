fn main() {
    let protoc = protoc_bin_vendored::protoc_bin_path()
        .expect("failed to locate vendored protoc");
    std::env::set_var("PROTOC", protoc);

    tonic_build::configure()
        .compile_protos(&["../communication/zeus_core.proto"], &["../communication"])
        .expect("failed to compile protos");
}
